import json
import logging
import os
import re
import shutil
import signal
import sys
import threading
import time
from subprocess import call

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Tuple

import faster_whisper
from mutagen.mp3 import MP3
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filename='uultra.log',  # Log file path
                    filemode='a'  # Append mode, use 'w' for overwrite mode
                    )


class Config:
    MODEL_SIZE: str = "large-v3"
    BEAM_SIZE: int = 9
    PATIENCE: int = 924
    BEST_OF: int = 9
    LANGUAGE: str = "en"
    MIN_SILENCE_DURATION_MS: int = 500
    THRESHOLD: float = 0.55
    TEMPERATURE: Tuple[float, float, float] = (0.01, 0.03, 0.1)
    REPETITION_PENALTY: float = 1.1
    WINDOW_SIZE_SAMPLES: int = 3072
    COMPRESSION_RATIO_THRESHOLD: float = 1.9
    LOG_PROB_THRESHOLD: float = -1.0
    NO_SPEECH_THRESHOLD: float = 0.55
    CONDITION_ON_PREVIOUS_TEXT: bool = True
    PROMPT_RESET_ON_TEMPERATURE: float = 0.5


class MP3Handler(FileSystemEventHandler):
    def __init__(self, base_directory: str, too_short_directory: str) -> None:
        self.base_directory: str = os.path.abspath(base_directory)
        self.too_short_directory: str = os.path.abspath(too_short_directory)
        self.duration_threshold: float = 4.0
        self.duration_pool: ThreadPoolExecutor = ThreadPoolExecutor(
            max_workers=15)
        self.transcription_pool: ThreadPoolExecutor = ThreadPoolExecutor(
            max_workers=3)
        self.model: Any = faster_whisper.WhisperModel(
            Config.MODEL_SIZE, device="cuda")
        os.makedirs(self.too_short_directory, exist_ok=True)
        self.file_locks = {}  # Dictionary to maintain locks for files
        self.file_times = {}  # Tracks last process time for debouncing
        # Process a file only if it hasn't been processed in the last second
        self.debounce_seconds = 1
        self.observer = Observer()
        self.observer.schedule(self, self.base_directory, recursive=True)

    def on_created(self, event: Any) -> None:
        if not event.is_directory and event.src_path.endswith('.mp3'):
            file_path = os.path.abspath(event.src_path)
            current_time = time.time()
            last_processed = self.file_times.get(file_path, 0)
            if current_time - last_processed > self.debounce_seconds:
                self.file_times[file_path] = current_time
                logging.info(f"New MP3 file detected: {file_path}")
                self.process_file(file_path)

    def start(self):
        # Initially process existing .mp3 files in the root directory
        self.process_existing_files()
        # Start monitoring for new files
        self.observer.schedule(self, self.base_directory, recursive=False)
        self.observer.start()
        try:
            # Keep the main thread alive
            self.observer.join()
        except KeyboardInterrupt:
            self.stop()

    def process_existing_files(self):
        for root, dirs, files in os.walk(self.base_directory, topdown=True):
            for filename in files:
                if filename.endswith('.mp3'):
                    full_path = os.path.join(root, filename)
                    if os.path.dirname(full_path) == self.base_directory:
                        self.process_file(full_path)

    def stop(self):
        self.observer.stop()
        self.observer.join()
        self.duration_pool.shutdown(wait=True)
        self.transcription_pool.shutdown(wait=True)
        logging.info("Monitoring stopped.")
        sys.exit(0)

    def process_file(self, path: str) -> None:
        if not path.endswith('.mp3'):
            return
        file_dir = os.path.dirname(os.path.abspath(path))
        if file_dir != self.base_directory:
            logging.debug(f"Ignoring file not in root directory: {path}")
            return
        try:
            audio = MP3(path)
            duration = audio.info.length
            logging.info(f"Processed {path}: Duration = {duration} seconds")
            if duration < self.duration_threshold:
                dest_path = os.path.join(
                    self.too_short_directory, os.path.basename(path))
                shutil.move(path, dest_path)
                logging.info(f"Moved {path} to {dest_path} due to short duration.")
            else:
                self.transcription_pool.submit(self.transcribe_and_move, path)
        except Exception as e:
            logging.error(f"Failed to process {path}: {str(e)}")
            temp_path = self.get_temp_path(path)
            try:
                # Re-encode the file to potentially fix issues
                call(['ffmpeg', '-i', path, temp_path])
                # Ensure the file exists before attempting to process it
                if os.path.exists(temp_path):
                    # Attempt to re-process the re-encoded file
                    audio = MP3(temp_path)
                    duration = audio.info.length
                    logging.info(f"Re-processed {temp_path}: Duration = {duration} seconds")
                    if duration < self.duration_threshold:
                        final_path = os.path.join(
                            self.too_short_directory, os.path.basename(path))
                        os.remove(path)  # Delete the original file
                        os.rename(temp_path, final_path)  # Rename temp file to original filename
                        logging.info(f"Moved and renamed {temp_path} to {final_path} due to short duration.")
                    else:
                        # File passes the threshold, so move it for transcription
                        final_path = os.path.join(self.base_directory, os.path.basename(path))
                        os.remove(path)  # Delete the original file
                        os.rename(temp_path, final_path)  # Rename temp file to original filename
                        self.transcription_pool.submit(self.transcribe_and_move, final_path)
                else:
                    logging.error(f"Re-encoded file not found: {temp_path}")
                    raise FileNotFoundError(f"Re-encoded file not found: {temp_path}")
            except Exception as re:
                logging.error(f"Failed to re-process {path} after re-encoding: {str(re)}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)  # Delete the temporary re-encoded file
                original_dest_path = os.path.join(
                    self.too_short_directory, os.path.basename(path))
                shutil.move(path, original_dest_path)
                logging.info(f"Moved original {path} to {original_dest_path} after repeated failures.")

    def get_temp_path(self, original_path: str) -> str:
        # Generate a temporary file path in the too_short_directory with '_temp' suffix
        base, ext = os.path.splitext(original_path)
        if not base.endswith('_temp'):
            temp_base = os.path.basename(base) + '_temp' + ext
            return os.path.join(self.too_short_directory, temp_base)
        else:
            return original_path  # Already processed, return as is

    def transcribe_and_move(self, path: str) -> None:
        lock = self.file_locks.setdefault(path, threading.Lock())
        with lock:  # Ensure that no other thread can work on this file while it's being processed
            if not os.path.exists(path):
                logging.error(
                    f"File not found, skipping transcription: {path}")
                return

            try:
                segments, info = self.model.transcribe(
                    path,
                    beam_size=Config.BEAM_SIZE,
                    patience=Config.PATIENCE,
                    best_of=Config.BEST_OF,
                    no_speech_threshold=Config.NO_SPEECH_THRESHOLD,
                    log_prob_threshold=Config.LOG_PROB_THRESHOLD,
                    compression_ratio_threshold=Config.COMPRESSION_RATIO_THRESHOLD,
                    repetition_penalty=Config.REPETITION_PENALTY,
                    condition_on_previous_text=Config.CONDITION_ON_PREVIOUS_TEXT,
                    prompt_reset_on_temperature=Config.PROMPT_RESET_ON_TEMPERATURE,
                    initial_prompt="", temperature=Config.TEMPERATURE, vad_filter=True,
                    vad_parameters={"threshold": Config.THRESHOLD,
                                    "min_silence_duration_ms": Config.MIN_SILENCE_DURATION_MS,
                                    "window_size_samples": Config.WINDOW_SIZE_SAMPLES},
                    language=Config.LANGUAGE
                )

                formatted_result = self.format_segments(segments)
                transcription_text = json.loads(formatted_result)['text']

                talkgroup_id = self.extract_talkgroup_id(
                    os.path.basename(path))
                final_directory = os.path.join(
                    self.base_directory, talkgroup_id)
                os.makedirs(final_directory, exist_ok=True)

                # Removing '.mp3' extension from filename before appending '.txt'
                base_filename = os.path.splitext(os.path.basename(path))[0]
                transcription_path = os.path.join(
                    final_directory, base_filename + ".txt")

                with open(transcription_path, 'w') as f:
                    f.write(transcription_text)
                final_mp3_path = os.path.join(
                    final_directory, os.path.basename(path))
                shutil.move(path, final_mp3_path)
                logging.info(
                    f"Transcribed and moved {path} to {final_directory}")
            except Exception as e:
                logging.error(f"Failed to transcribe {path}: {str(e)}")
            finally:
                del self.file_locks[path]  # Remove lock after processing

    def format_segments(self, segments):
        formatted_segments = [{"text": segment.text} for segment in segments]
        formatted_text = " ".join(segment['text'].strip()
                                  for segment in formatted_segments)
        return json.dumps({"text": formatted_text}).replace('": "', '":"')

    def extract_talkgroup_id(self, filename: str) -> str:
        # Updated regex to match 'TO_12345.' or 'TO_1234_'
        match: re.Match = re.search(r"TO_(\d+)[._]", filename)
        return match.group(1) if match else "unknown"


def start_monitoring(base_directory: str, too_short_directory: str) -> None:
    handler = MP3Handler(base_directory, too_short_directory)
    signal.signal(signal.SIGINT, lambda sig, frame: handler.stop())
    handler.start()


def signal_handler(signal_received: signal.Signals, frame: Any) -> None:
    logging.info('SIGINT or CTRL-C detected. Exiting gracefully')
    global handler
    handler.stop()


if __name__ == "__main__":
    root_directory = "/home/USER/SDRTrunk/recordings"
    too_short_directory = "/home/USER/SDRTrunk/tooShortOrError"
    start_monitoring(root_directory, too_short_directory)
