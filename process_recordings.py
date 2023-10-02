# Standard library imports
import os
import time
import sqlite3
import xml.etree.ElementTree as ET
import re
import logging
import json

# Third-party imports
from pydub import AudioSegment
from functools import lru_cache
import openai
import requests

# Configurations
RECORDINGS_DIR = "/home/YOUR_USER/SDRTrunk/recordings"
XML_PATH = "/home/YOUR_USER/SDRTrunk/playlist/default.xml"
DATABASE_PATH = "/home/YOUR_USER/SDRTrunk/recordings.db"
TEN_SIGN_FILE = "/home/YOUR_USER/SDRTrunk/Some_Co_NC_TENSIGN.txt"
CALLSIGNS_PATH = "/home/YOUR_USER/SDRTrunk/callsigns.db"
NCSHP_TEN_SIGN_FILE = "/home/YOUR_USER/SDRTrunk/NCSHP_TENCODE.txt"
SIGNALS_FILE = "/home/YOUR_USER/SDRTrunk/NCSHP_SIGNALS.txt"
OPENAI_API_KEY = "YOUR_KEY"

# You could also just grab these from your SDRTrunk XML file
# if you already have accumulated a list of radio IDs there.
RADIO_ID_NAMES = {
    "1610092": "FCPD Dispatch",
    "1610051": "Sheriff Dispatch",
    "1610077": "EMS Dispatch",
    "2499936": "NCSHP Dispatch",
    "1610078": "RPD Dispatch",
    "1610018": "EMS CAD",
    "2499937": "NCSHP Dispatch",
    "1610019": "FD CAD",
}

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="script_log.log",
    filemode="a",
)
logger = logging.getLogger()


def get_formatted_radio_id(radio_id):
    name = RADIO_ID_NAMES.get(radio_id)
    if name:
        return f"{radio_id} ({name})"
    return radio_id


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


# Function to load 10-codes from the file
def load_ten_codes(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()
    ten_codes = {}
    for line in lines:
        code, description = line.strip().split(" ", 1)
        ten_codes[code] = description
    return ten_codes


# Function to load signals file
def load_signals(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()
    signals = {}
    for line in lines:
        signal, description = line.strip().split(" ", 1)
        signals[signal] = description
    return signals


def extract_ten_codes_from_transcription(transcription, ten_codes):
    extracted_codes = {}

    # Sort ten_codes by length in descending order before matching
    for code, description in sorted(
        ten_codes.items(), key=lambda x: len(x[0]), reverse=True
    ):
        normalized_code = normalize_ten_code(code, transcription)
        if normalized_code:
            extracted_codes[code] = description
            transcription = transcription.replace(normalized_code, code)

    return extracted_codes, transcription


def normalize_ten_code(code, transcription):
    code_with_hyphen = code
    code_without_hyphen = code.replace("10-", "10")

    pattern = (
        r"(?<!\d)("
        + re.escape(code_with_hyphen)
        + r"|"
        + re.escape(code_without_hyphen)
        + r")(?!\d)"
    )
    match = re.search(pattern, transcription)
    if match:
        return match.group()
    return None


def extract_callsigns_from_transcription(transcription, callsigns):
    extracted_callsigns = {}

    for callsign, name in callsigns.items():
        if callsign in transcription:
            logger.info(f"Detected callsign: {callsign}")
            extracted_callsigns[callsign] = name

    return extracted_callsigns


def extract_signals_from_transcription(transcription, signals):
    extracted_signals = {}

    # Sort signals by length in descending order before matching
    for signal, description in sorted(
        signals.items(), key=lambda x: len(x[0]), reverse=True
    ):
        if signal in transcription:
            extracted_signals[signal] = description
            transcription = transcription.replace(signal, "")

    return extracted_signals, transcription


def update_transcription_to_json(
    transcription, ten_codes, callsigns, radio_id, signals=None
):
    extracted_codes, updated_transcription = extract_ten_codes_from_transcription(
        transcription, ten_codes
    )
    extracted_callsigns = extract_callsigns_from_transcription(
        updated_transcription, callsigns
    )

    # If signals provided, extract from transcription
    if signals:
        extracted_signals, updated_transcription = extract_signals_from_transcription(
            updated_transcription, signals
        )
    else:
        extracted_signals = {}

    result = {radio_id: updated_transcription}
    result.update(extracted_codes)
    result.update(extracted_callsigns)
    result.update(extracted_signals)

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


def connect_to_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()
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
    return conn, cur


def process_file(file):
    logger.info(f"Processing file: {file}")
    if not file.endswith(".mp3"):
        return

    full_path = os.path.join(RECORDINGS_DIR, file)
    file_duration = get_file_duration(full_path)

    # Check duration and delete if less than 9 seconds
    if round(float(file_duration)) < 9:
        os.remove(full_path)
        return

    (
        date,
        time_str,
        unixtime,
        talkgroup_id,
        only_radio_id,
        new_path,
    ) = extract_file_details(file, full_path)

    # Conditionally load ten codes based on talkgroup_id
    if talkgroup_id in ["52198", "52201"]:
        ten_codes = load_ten_codes(NCSHP_TEN_SIGN_FILE)
        signals = load_signals(SIGNALS_FILE)
    else:
        ten_codes = load_ten_codes(TEN_SIGN_FILE)
        signals = None

    transcription = curl_transcribe_audio(new_path)
    logger.info(f"Transcribed text for {file}: {transcription}")

    updated_transcription_json = format_transcription(
        transcription, ten_codes, only_radio_id, signals
    )

    write_transcription_to_file(new_path, updated_transcription_json)

    talkgroup_name = get_talkgroup_name(XML_PATH, talkgroup_id)

    return (
        date,
        time_str,
        unixtime,
        talkgroup_id,
        only_radio_id,
        file_duration,
        file,
        new_path,
        transcription,
        updated_transcription_json,
        talkgroup_name,
    )


def format_transcription(transcription, ten_codes, radio_id, signals=None):
    callsign_data = load_callsigns()
    radio_id = get_formatted_radio_id(radio_id)
    return update_transcription_to_json(
        transcription, ten_codes, callsign_data, radio_id, signals
    )


def get_file_duration(full_path):
    audio = AudioSegment.from_mp3(full_path)
    return str(len(audio) / 1000)


def extract_file_details(file, full_path):
    date, time_part = file.split("_")[:2]
    time_str = time_part[:2] + ":" + time_part[2:4]
    unixtime = int(time.mktime(time.strptime(date + " " + time_str, "%Y%m%d %H:%M")))
    talkgroup_id = file.split("TO_")[1].split("_")[0]
    only_radio_id = extract_radio_id(file)
    new_path = move_file_based_on_talkgroup(full_path, file, talkgroup_id)
    return date, time_str, unixtime, talkgroup_id, only_radio_id, new_path


def move_file_based_on_talkgroup(full_path, file, talkgroup_id):
    new_dir = os.path.join(RECORDINGS_DIR, talkgroup_id)
    if not os.path.exists(new_dir):
        os.mkdir(new_dir)
    new_path = os.path.join(new_dir, file)
    os.rename(full_path, new_path)
    return new_path


def write_transcription_to_file(new_path, updated_transcription_json):
    try:
        logger.info(f"Starting to write to text file for {new_path}")
        with open(new_path.replace(".mp3", ".txt"), "w") as text_file:
            text_file.write(updated_transcription_json)
    except Exception as e:
        logger.error(f"Error while writing to text file: {str(e)}")


def insert_into_database(cur, data):
    try:
        logger.info(
            f"Preparing to insert into SQLite for {data[6]}: Date-{data[0]}, Time-{data[1]}, UnixTime-{data[2]}, TalkgroupID-{data[3]}, RadioID-{data[4]}, Duration-{data[5]}, Path-{data[7]}, Transcription-{data[8]}"
        )
        cur.execute(
            """
            INSERT INTO recordings (date, time, unixtime, talkgroup_id, talkgroup_name, radio_id, duration, filename, filepath, transcription, v2transcription)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            data,
        )
    except Exception as e:
        logger.error(f"Error while inserting into database: {str(e)}")


def main():
    conn, cur = connect_to_database()
    for file in os.listdir(RECORDINGS_DIR):
        data = process_file(file)
        if data:
            insert_into_database(cur, data)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
