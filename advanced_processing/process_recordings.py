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
import shutil

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
    """
    Returns a formatted string containing the radio ID and its corresponding name (if available).

    Args:
        radio_id (str): The radio ID to format.

    Returns:
        str: A formatted string containing the radio ID and its corresponding name (if available).
    """
    name = RADIO_ID_NAMES.get(radio_id)
    if name:
        return f"{radio_id} ({name})"
    return radio_id


def load_callsigns():
    """
    Load the most recent data for each unique callsign from the callsign_data table in the SQLite database located at CALLSIGNS_PATH.

    Returns:
    dict: A dictionary where the keys are callsigns and the values are the corresponding names.
    """
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


def load_ten_codes(file_path):
    """
    Load ten codes from a file and return a dictionary of code-description pairs.

    Args:
        file_path (str): The path to the file containing ten codes.

    Returns:
        dict: A dictionary of ten codes with their descriptions.
    """
    with open(file_path, "r") as f:
        lines = f.readlines()
    ten_codes = {}
    for line in lines:
        code, description = line.strip().split(" ", 1)
        ten_codes[code] = description
    return ten_codes


def load_signals(file_path):
    """
    Load signals from a file and return them as a dictionary.

    Args:
        file_path (str): The path to the file containing the signals.

    Returns:
        dict: A dictionary containing the signals and their descriptions.
    """
    with open(file_path, "r") as f:
        lines = f.readlines()
    signals = {}
    for line in lines:
        signal, description = line.strip().split(" ", 2)[0:2]  # Get the first two words as the signal
        signal_key = " ".join(signal)  # Combine them to form the key
        signals[signal_key.lower()] = description  # Convert to lowercase
    return signals


def extract_ten_codes_from_transcription(transcription, ten_codes):
    """
    Extracts ten codes from a given transcription using a dictionary of ten codes.

    Args:
        transcription (str): The transcription to extract ten codes from.
        ten_codes (dict): A dictionary of ten codes to match against.

    Returns:
        A tuple containing a dictionary of extracted ten codes and the updated transcription with the extracted codes removed.
    """
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
    """
    Normalizes a 10-code by replacing any occurrences of "10-" with "10" in the given code,
    and then searches for the normalized code in the given transcription using a regular expression.
    If a match is found, returns the matched code. Otherwise, returns None.

    Args:
        code (str): The 10-code to normalize and search for.
        transcription (str): The text to search for the normalized 10-code in.

    Returns:
        str or None: The matched 10-code if found, or None if not found.
    """
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
    """
    Extracts callsigns from a given transcription and returns a dictionary of extracted callsigns and their corresponding names.

    Args:
        transcription (str): The transcription to extract callsigns from.
        callsigns (dict): A dictionary of callsigns and their corresponding names.

    Returns:
        dict: A dictionary of extracted callsigns and their corresponding names.
    """
    extracted_callsigns = {}

    for callsign, name in callsigns.items():
        if callsign in transcription:
            logger.info(f"Detected callsign: {callsign}")
            extracted_callsigns[callsign] = name

    return extracted_callsigns


def extract_signals_from_transcription(transcription, signals):
    """
    Extracts signals from a given transcription by matching them with a dictionary of known signals.

    Args:
        transcription (str): The transcription to extract signals from.
        signals (dict): A dictionary of known signals and their descriptions.

    Returns:
        tuple: A tuple containing a dictionary of extracted signals and their descriptions, and the remaining transcription
               after all extracted signals have been removed.
    """
    extracted_signals = {}
    transcription_lower = transcription.lower()  # Convert to lowercase

    for signal, description in sorted(
        signals.items(), key=lambda x: len(x[0]), reverse=True
    ):
        if signal.lower() in transcription_lower:  # Convert to lowercase
            extracted_signals[signal] = description
            # Uncomment the next line if you want to remove the signal from the transcription
            # transcription_lower = transcription_lower.replace(signal.lower(), "")

    return extracted_signals, transcription

def update_transcription_to_json(
    transcription, ten_codes, callsigns, radio_id, signals=None
):
    """
    Update the transcription with extracted ten codes, callsigns, and signals and return the result as a JSON string.

    Args:
        transcription (str): The original transcription to update.
        ten_codes (list): A list of ten codes to extract from the transcription.
        callsigns (list): A list of callsigns to extract from the transcription.
        radio_id (str): The ID of the radio.
        signals (dict, optional): A dictionary of extracted signals and their descriptions. Defaults to None.

    Returns:
        str: A JSON string containing the updated transcription, extracted ten codes, callsigns, and signals.
    """
    extracted_codes, updated_transcription = extract_ten_codes_from_transcription(
        transcription, ten_codes
    )
    extracted_callsigns = extract_callsigns_from_transcription(
        updated_transcription, callsigns
    )

    result = {radio_id: updated_transcription}
    result.update(extracted_codes)
    result.update(extracted_callsigns)
    if signals:
        result.update(signals)  # Integrating the signal descriptions

    return json.dumps(result)


@lru_cache(maxsize=None)
def get_talkgroup_name(xml_path: str, talkgroup_id: str) -> str:
    """
    Given an XML file path and a talkgroup ID, returns the name of the talkgroup.

    Args:
        xml_path (str): The path to the XML file containing talkgroup information.
        talkgroup_id (str): The ID of the talkgroup to retrieve the name for.

    Returns:
        str: The name of the talkgroup with the given ID, or None if the ID is not found.
    """
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
    """
    Transcribes audio from a file using OpenAI's Audio API.

    Args:
        file_path (str): The path to the audio file to transcribe.

    Returns:
        str: The transcription of the audio file.
    """
    openai.api_key = OPENAI_API_KEY
    audio_file = open(file_path, "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    return str(transcript)


def curl_transcribe_audio(file_path):
    """
    Transcribes audio from a file using OpenAI's API.

    Args:
        file_path (str): The path to the audio file to be transcribed.

    Returns:
        str: The transcription of the audio file in JSON format.
    """
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
    """
    Extracts the radio ID from a given filename.

    Args:
        filename (str): The name of the file to extract the radio ID from.

    Returns:
        str: The extracted radio ID if found, otherwise "Unknown ID".
    """
    match = re.search(r"FROM_(\d+)", filename)
    if match:
        return match.group(1)
    else:
        return "Unknown ID"


def connect_to_database():
    """
    Connects to the database and creates a table if it doesn't exist.

    Returns:
    conn (sqlite3.Connection): Connection object to the database.
    cur (sqlite3.Cursor): Cursor object to execute SQL queries.
    """
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
    """
    Process a given audio file by transcribing it, formatting the transcription,
    and writing the formatted transcription to a file.

    Args:
        file (str): The name of the audio file to process.

    Returns:
        tuple: A tuple containing the following information:
            - date (str): The date of the recording.
            - time_str (str): The time of the recording in string format.
            - unixtime (float): The time of the recording in Unix time format.
            - talkgroup_id (str): The ID of the talkgroup associated with the recording.
            - only_radio_id (str): The ID of the radio associated with the recording.
            - file_duration (float): The duration of the audio file in seconds.
            - file (str): The name of the audio file.
            - new_path (str): The path to the processed audio file.
            - transcription (str): The raw transcription of the audio file.
            - updated_transcription_json (str): The formatted transcription of the audio file in JSON format.
            - talkgroup_name (str): The name of the talkgroup associated with the recording.
    """
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
    if talkgroup_id in ["52198", "52199", "52201"]:
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
        talkgroup_name,
        only_radio_id,
        file_duration,
        file,
        new_path,
        transcription,
        updated_transcription_json,
    )


def format_transcription(transcription, ten_codes, radio_id, signals=None):
    """
    Formats the given transcription with the provided ten codes, radio ID, and signals data.

    Args:
        transcription (str): The transcription to format.
        ten_codes (dict): A dictionary of ten codes to use for formatting.
        radio_id (str): The radio ID to use for formatting.
        signals (list, optional): A list of signals data to use for formatting.

    Returns:
        dict: The formatted transcription as a dictionary.
    """
    callsign_data = load_callsigns()
    radio_id = get_formatted_radio_id(radio_id)

    # Extract signals from transcription
    # Check if signals is not None before attempting to extract
    if signals:
        extracted_signals, new_transcription = extract_signals_from_transcription(transcription, signals)
    else:
        extracted_signals = {}
        new_transcription = transcription

    return update_transcription_to_json(
        new_transcription, ten_codes, callsign_data, radio_id, extracted_signals
    )


def get_file_duration(full_path):
    """
    Returns the duration of an audio file in seconds.

    Args:
        full_path (str): The full path of the audio file.

    Returns:
        str: The duration of the audio file in seconds.
    """
    audio = AudioSegment.from_mp3(full_path)
    return str(len(audio) / 1000)


def extract_file_details(file, full_path):
    """
    Extracts details from a given file name and full path.

    Args:
        file (str): The name of the file.
        full_path (str): The full path of the file.

    Returns:
        tuple: A tuple containing the following details:
            - date (str): The date of the recording in YYYYMMDD format.
            - time_str (str): The time of the recording in HH:MM format.
            - unixtime (int): The Unix timestamp of the recording.
            - talkgroup_id (str): The ID of the talkgroup.
            - only_radio_id (str): The ID of the radio.
            - new_path (str): The new path of the file after it has been moved based on the talkgroup ID.
    """
    date, time_part = file.split("_")[:2]
    time_str = time_part[:2] + ":" + time_part[2:4]
    unixtime = int(time.mktime(time.strptime(date + " " + time_str, "%Y%m%d %H:%M")))
    talkgroup_id = file.split("TO_")[1].split("_")[0]
    only_radio_id = extract_radio_id(file)
    new_path = move_file_based_on_talkgroup(full_path, file, talkgroup_id)
    return date, time_str, unixtime, talkgroup_id, only_radio_id, new_path


def move_file_based_on_talkgroup(full_path: str, file: str, talkgroup_id: str) -> str:
    """
    Moves a file to a directory based on its talkgroup ID.

    Args:
        full_path (str): The full path of the file to be moved.
        file (str): The name of the file to be moved.
        talkgroup_id (str): The talkgroup ID used to determine the directory to move the file to.

    Returns:
        str: The new path of the moved file.
    """
    new_dir = os.path.join(RECORDINGS_DIR, talkgroup_id)
    if not os.path.exists(new_dir):
        os.mkdir(new_dir)
    new_path = os.path.join(new_dir, file)
    os.rename(full_path, new_path)
    return new_path


def write_transcription_to_file(new_path, updated_transcription_json):
    """
    Writes the updated transcription JSON to a text file with the same name as the input audio file, but with a .txt extension.

    Args:
        new_path (str): The path to the input audio file.
        updated_transcription_json (str): The updated transcription JSON to be written to the text file.

    Raises:
        Exception: If there is an error while writing to the text file.

    Returns:
        None
    """
    try:
        logger.info(f"Starting to write to text file for {new_path}")
        with open(new_path.replace(".mp3", ".txt"), "w") as text_file:
            text_file.write(updated_transcription_json)
    except Exception as e:
        logger.error(f"Error while writing to text file: {str(e)}")


def insert_into_database(cur, data):
    """
    Inserts recording data into SQLite database.

    Args:
        cur: SQLite cursor object.
        data: Tuple containing recording data in the following order:
            (date, time, unixtime, talkgroup_id, talkgroup_name, radio_id, duration, filename, filepath, transcription, v2transcription)

    Returns:
        None
    """
    try:
        logger.info(
            f"Preparing to insert into SQLite for {data[6]}: Date-{data[0]}, Time-{data[1]}, UnixTime-{data[2]}, TalkgroupID-{data[3]}, TalkgroupName-{data[10]}, RadioID-{data[4]}, Duration-{data[5]}, Path-{data[7]}, Transcription-{data[8]}, v2Trans-{data[9]}"
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


def find_and_move_mp3_without_txt():
    """
    Find MP3 files in subdirectories of RECORDINGS_DIR that do not have an associated TXT file,
    and move them back to the root directory for processing.
    """
    for subdir, _, files in os.walk(RECORDINGS_DIR):
        if subdir == RECORDINGS_DIR:  # Skip the root directory
            continue

        mp3_files = [f for f in files if f.endswith('.mp3')]
        txt_files = [f.replace('.txt', '') for f in files if f.endswith('.txt')]

        moved_files = []

        for mp3 in mp3_files:
            mp3_base = mp3.replace('.mp3', '')
            if mp3_base not in txt_files:
                logger.info(f"Moving {mp3} to root directory")
                src_path = os.path.join(subdir, mp3)
                dest_path = os.path.join(RECORDINGS_DIR, mp3)
                shutil.move(src_path, dest_path)  # Move the file
                moved_files.append(mp3)


def main():
    """
    Process all recordings in the specified directory and insert the data into a database.

    Returns:
        None
    """
    find_and_move_mp3_without_txt()
    conn, cur = connect_to_database()
    for file in os.listdir(RECORDINGS_DIR):
        data = process_file(file)
        if data:
            insert_into_database(cur, data)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
