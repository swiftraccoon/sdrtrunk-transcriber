import os
import openai
import sqlite3
import xml.etree.ElementTree as ET
from pydub import AudioSegment
from functools import lru_cache
import time

# Configurations
RECORDINGS_DIR = '/home/user/SDRTrunk/recordings'
XML_PATH = '/home/user/SDRTrunk/playlist/default.xml'
DATABASE_PATH = '/home/user/SDRTrunk/recordings.db'


def get_duration(file_path):
    audio = AudioSegment.from_mp3(file_path)
    return len(audio)


@lru_cache(maxsize=None)
def get_talkgroup_name(xml_path, talkgroup_id):
    if not hasattr(get_talkgroup_name, 'talkgroup_dict'):
        # Parse the XML file and create a dictionary of talkgroup IDs and names
        tree = ET.parse(xml_path)
        root = tree.getroot()
        talkgroup_dict = {}
        for alias in root.findall('alias'):
            for id_element in alias.findall('id'):
                if id_element.get('type') == 'talkgroup':
                    talkgroup_dict[id_element.get('value')] = alias.get('name')
        get_talkgroup_name.talkgroup_dict = talkgroup_dict
    return get_talkgroup_name.talkgroup_dict.get(talkgroup_id)


def transcribe_audio(file_path):
    openai.api_key = "anAPIkeyShouldGoHere"
    audio_file = open(file_path, "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    return str(transcript)


def main():
    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()

    # Create the table if it doesn't exist
    cur.execute('''
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
        transcription TEXT
    )
    ''')

    for file in os.listdir(RECORDINGS_DIR):
        if file.endswith('.mp3'):
            full_path = os.path.join(RECORDINGS_DIR, file)
            
            # Check duration and delete if less than 14 seconds
            if get_duration(full_path) < 14 * 1000:
                os.remove(full_path)
                continue

            file_duration = str(get_duration(full_path) / 1000)
            
            # Extract details from filename
            date, time_part = file.split('_')[:2]
            time_str = time_part[:2] + ':' + time_part[2:4]
            unixtime = int(time.mktime(time.strptime(date + ' ' + time_str, '%Y%m%d %H:%M')))
            talkgroup_id = file.split('TO_')[1].split('_')[0]
            radio_id = file.split('FROM_')[1].split('.mp3')[0]
            
            # Move the file based on talkgroup ID
            new_dir = os.path.join(RECORDINGS_DIR, talkgroup_id)
            if not os.path.exists(new_dir):
                os.mkdir(new_dir)
            new_path = os.path.join(new_dir, file)
            os.rename(full_path, new_path)
            
            # Transcribe the audio
            transcription = transcribe_audio(new_path)
            
            # Save the transcription to a .txt file
            with open(new_path.replace('.mp3', '.txt'), 'w') as text_file:
                text_file.write(transcription)
            
            # Get the talkgroup name from XML
            talkgroup_name = get_talkgroup_name(XML_PATH, talkgroup_id)
            
            # Insert data into SQLite
            cur.execute('''
            INSERT INTO recordings (date, time, unixtime, talkgroup_id, talkgroup_name, radio_id, duration, filename, filepath, transcription)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (date, time_str, unixtime, talkgroup_id, talkgroup_name, radio_id, file_duration, file, new_path, transcription))

    conn.commit()
    conn.close()


if __name__ == '__main__':
    main()
