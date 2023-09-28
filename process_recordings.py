import os
import openai
import sqlite3
import xml.etree.ElementTree as ET
from pydub import AudioSegment
from functools import lru_cache
import time
import json
import logging
import re
import requests


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="script_log.log",
    filemode="a",
)
logger = logging.getLogger()


# Configurations
RECORDINGS_DIR = "/home/USER/SDRTrunk/recordings"
XML_PATH = "/home/USER/SDRTrunk/playlist/default.xml"
DATABASE_PATH = "/home/USER/SDRTrunk/recordings.db"
TEN_SIGN_FILE = "/home/USER/SDRTrunk/Rutherford_Co_NC_TENSIGN.txt"
CALLSIGNS_PATH = "/home/USER/SDRTrunk/callsigns.db"
OPENAI_API_KEY = "KEY"


radio_id_names = {
    1610092: "FCPD Dispatch",
    1610051: "Sheriff Dispatch",
    1610077: "EMS Dispatch",
    2499936: "NCSHP Dispatch",
    1610078: "RPD Dispatch",
}


def get_formatted_radio_id(radio_id):
    name = radio_id_names.get(radio_id)
    if name:
        return f"{radio_id} ({name})"
    return radio_id


def get_duration(file_path):
    audio = AudioSegment.from_mp3(file_path)
    return len(audio)


def load_callsigns():
    conn = sqlite3.connect(CALLSIGNS_PATH)
    cur = conn.cursor()

    # Fetch the most recent data for each unique callsign
    cur.execute(
        """
    SELECT c1.callsign, c1.name
    FROM callsign_data c1
    JOIN (
        SELECT callsign, MAX(timestamp) as max_timestamp
        FROM callsign_data
        GROUP BY callsign
    ) c2 ON c1.callsign = c2.callsign AND c1.timestamp = c2.max_timestamp
    """
    )

    callsigns = {}
    for row in cur.fetchall():
        callsigns[row[0]] = row[1]

    conn.close()
    return callsigns


#
# Function to load 10-codes from the file
def load_ten_codes(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()
    ten_codes = {}
    for line in lines:
        code, description = line.strip().split(" ", 1)
        ten_codes[code] = description
    return ten_codes


# Function to update the transcription with 10-codes, callsigns, and radio id
def update_transcription_to_json(transcription, ten_codes, callsigns, radio_id):
    extracted_codes = {}
    extracted_callsigns = {}

    # Sort ten_codes by length in descending order before matching
    for code, description in sorted(
        ten_codes.items(), key=lambda x: len(x[0]), reverse=True
    ):
        # Look for the code with non-digit boundaries
        pattern = r"(?<!\d)" + re.escape(code) + r"(?!\d)"
        if re.search(pattern, transcription):
            extracted_codes[code] = description
            # transcription = transcription.replace(code, f"{code} [{description}]")

    # Detect callsigns in transcription
    for callsign, name in callsigns.items():
        # logger.debug(f"Checking for callsign: {callsign}")
        if callsign in transcription:
            logger.info(f"Detected callsign: {callsign}")
            extracted_callsigns[callsign] = name

    result = {radio_id: transcription}
    result.update(extracted_codes)  # Merge ten codes into result
    result.update(extracted_callsigns)  # Merge callsigns into result

    # transcribed = json.loads(json.dumps(result))
    # for key in transcribed:
    #     transcribed[key] = json.loads(transcribed[key])
    # encoded = json.dumps(transcribed, indent=4)

    return json.dumps(result)


@lru_cache(maxsize=None)
def get_talkgroup_name(xml_path, talkgroup_id):
    if not hasattr(get_talkgroup_name, "talkgroup_dict"):
        # Parse the XML file and create a dictionary of talkgroup IDs and names
        tree = ET.parse(xml_path)
        root = tree.getroot()
        talkgroup_dict = {}
        for alias in root.findall("alias"):
            for id_element in alias.findall("id"):
                if id_element.get("type") == "talkgroup":
                    talkgroup_dict[id_element.get("value")] = alias.get("name")
        get_talkgroup_name.talkgroup_dict = talkgroup_dict
    return get_talkgroup_name.talkgroup_dict.get(talkgroup_id)


def pyapi_transcribe_audio(file_path):
    openai.api_key = OPENAI_API_KEY
    audio_file = open(file_path, "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    return str(transcript)


def curl_transcribe_audio(file_path):
    # Define the endpoint and your API key
    url = "https://api.openai.com/v1/audio/transcriptions"
    api_key = OPENAI_API_KEY

    # Setup headers
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    # Open the file and setup files and data to be sent
    with open(file_path, "rb") as file:
        files = {
            "file": file,
        }
        data = {
            "model": "whisper-1",
            "prompt": "Transcribe the radio dispatch audio. The speaker is usually a dispatcher, police officer, or EMS responder. There are often callsigns, ten-codes, and addresses said.",
            "response_format": "json",
            "temperature": "0",
            "language": "en",
        }

        # Make the POST request
        response = requests.post(url, headers=headers, files=files, data=data)

    # Print the response or handle as needed
    return str(response.json())


def extract_radio_id(filename):
    match = re.search(r"FROM_(\d+)", filename)
    if match:
        return match.group(1)
    else:
        return "Unknown ID"


def main():
    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()

    # Load 10-codes
    ten_codes = load_ten_codes(TEN_SIGN_FILE)

    # Create the table if it doesn't exist
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS recordings (
        date TEXT,
        time TEXT,
        unixtime INTEGER,
        talkgroup_id INTEGER,
        talkgroup_name TEXT,
        radio_id INTEGER,
        duration TEXT,
        filename TEXT,
        filepath TEXT,
        transcription TEXT,
        v2transcription TEXT
    )
    """
    )

    for file in os.listdir(RECORDINGS_DIR):
        logger.info(f"Processing file: {file}")
        if file.endswith(".mp3"):
            full_path = os.path.join(RECORDINGS_DIR, file)

            file_duration = str(get_duration(full_path) / 1000)

            # Check duration and delete if less than 14 seconds
            if round(float(file_duration)) < 14:
                os.remove(full_path)
                # logger.warning(
                #     f"File {file} removed due to short duration of {file_duration}"
                # )
                continue

            # Extract details from filename
            date, time_part = file.split("_")[:2]
            time_str = time_part[:2] + ":" + time_part[2:4]
            unixtime = int(
                time.mktime(time.strptime(date + " " + time_str, "%Y%m%d %H:%M"))
            )
            talkgroup_id = file.split("TO_")[1].split("_")[0]
            only_radio_id = extract_radio_id(file)
            radio_id = get_formatted_radio_id(only_radio_id)

            # Move the file based on talkgroup ID
            new_dir = os.path.join(RECORDINGS_DIR, talkgroup_id)
            if not os.path.exists(new_dir):
                os.mkdir(new_dir)
            new_path = os.path.join(new_dir, file)
            os.rename(full_path, new_path)

            # Transcribe the audio
            transcription = curl_transcribe_audio(new_path)
            logger.info(f"Transcribed text for {file}: {transcription}")

            # Update transcription with 10-codes and callsigns
            callsign_data = load_callsigns()
            updated_transcription_json = str(
                update_transcription_to_json(
                    transcription, ten_codes, callsign_data, radio_id
                )
            )

            try:
                logger.info(f"Starting to write to text file for {file}")
                with open(new_path.replace(".mp3", ".txt"), "w") as text_file:
                    text_file.write(updated_transcription_json)
            except Exception as e:
                logger.error(f"Error while writing to text file: {str(e)}")

            # Get the talkgroup name from XML
            talkgroup_name = get_talkgroup_name(XML_PATH, talkgroup_id)

            # Insert data into SQLite
            try:
                logger.info(
                    f"Preparing to insert into SQLite for {file}: Date-{date}, Time-{time_str}, UnixTime-{unixtime}, TalkgroupID-{talkgroup_id}, RadioID-{radio_id}, Duration-{file_duration}, Path-{new_path}, Transcription-{transcription}"
                )
                cur.execute(
                    """
                INSERT INTO recordings (date, time, unixtime, talkgroup_id, talkgroup_name, radio_id, duration, filename, filepath, transcription, v2transcription)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        date,
                        time_str,
                        unixtime,
                        talkgroup_id,
                        talkgroup_name,
                        radio_id,
                        file_duration,
                        file,
                        new_path,
                        transcription,
                        updated_transcription_json,
                    ),
                )
            except Exception as e:
                logger.error(f"Error while inserting into database: {str(e)}")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
