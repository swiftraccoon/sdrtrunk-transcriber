# pyre-strict
import logging
import os
import sys
import threading
import time

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from mutagen.mp3 import MP3

from config import Config
from transcriber import Transcriber
from utils import move_file, reencode_file

class MP3Handler(FileSystemEventHandler):
    """
    Handles events for .mp3 files in a directory, checking their duration and
    transcribing them if they are long enough.
    """
    def __init__(self, base_directory: str, too_short_directory: str) -> None:
        super().__init__()
        self.base_directory: str = os.path.abspath(base_directory)
        self.too_short_directory: str = os.path.abspath(too_short_directory)
        self.duration_threshold: float = Config.DURATION_THRESHOLD
        self.transcriber = Transcriber()
        self.file_locks: Dict[str, threading.Lock] = {}
        self.file_times: Dict[str, float] = {}
        self.debounce_seconds: float = Config.DEBOUNCE_SECONDS

        self.duration_pool = ThreadPoolExecutor(max_workers=15)
        self.transcription_pool = ThreadPoolExecutor(max_workers=3)

        # Ensure output directories exist
        os.makedirs(self.too_short_directory, exist_ok=True)

        self.observer = Observer()
        self.observer.schedule(self, self.base_directory, recursive=True)

    def on_created(self, event: Any) -> None:
        """
        Called when a new file is created. If it's an MP3 file,
        process it after debouncing to avoid repeated processing.
        """
        if not event.is_directory and event.src_path.endswith('.mp3'):
            file_path = os.path.abspath(event.src_path)
            current_time = time.time()
            last_processed = self.file_times.get(file_path, 0)
            if current_time - last_processed > self.debounce_seconds:
                self.file_times[file_path] = current_time
                logging.info(f"New MP3 file detected: {file_path}")
                self.process_file(file_path)

    def start(self) -> None:
        """
        Start monitoring the directory for new mp3 files.
        Also process any existing .mp3 files that might be present.
        """
        self.process_existing_files()
        self.observer.schedule(self, self.base_directory, recursive=False)
        self.observer.start()
        try:
            self.observer.join()
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """
        Stop monitoring and shut down executor pools gracefully.
        """
        self.observer.stop()
        self.observer.join()
        self.duration_pool.shutdown(wait=True)
        self.transcription_pool.shutdown(wait=True)
        logging.info("Monitoring stopped.")
        sys.exit(0)

    def process_existing_files(self) -> None:
        """
        Process all existing mp3 files in the base directory.
        """
        for root, dirs, files in os.walk(self.base_directory, topdown=True):
            for filename in files:
                if filename.endswith('.mp3'):
                    full_path = os.path.join(root, filename)
                    if os.path.dirname(full_path) == self.base_directory:
                        self.process_file(full_path)

    def process_file(self, path: str) -> None:
        """
        Checks the duration of the mp3 file. If too short, moves it.
        Otherwise, sends it for transcription.
        """
        if not path.endswith('.mp3'):
            return
        file_dir = os.path.dirname(os.path.abspath(path))
        if file_dir != self.base_directory:
            logging.debug(f"Ignoring file not in root directory: {path}")
            return
        try:
            duration = MP3(path).info.length
            logging.info(f"Processed {path}: Duration = {duration} seconds")
            if duration < self.duration_threshold:
                dest_path = os.path.join(self.too_short_directory, os.path.basename(path))
                move_file(path, dest_path)
                logging.info(f"Moved {path} to {dest_path} due to short duration.")
            else:
                self.transcription_pool.submit(self.transcribe_and_move, path)
        except Exception as e:
            logging.error(f"Failed to process {path}: {str(e)}")
            self._attempt_reencode(path)

    def _attempt_reencode(self, path: str) -> None:
        """
        Attempt to re-encode the file if processing fails the first time,
        and retry transcription logic.
        """
        temp_path = self._get_temp_path(path)
        if reencode_file(path, temp_path) and os.path.exists(temp_path):
            # Check duration again
            try:
                duration = MP3(temp_path).info.length
                logging.info(f"Re-processed {temp_path}: Duration = {duration} seconds")
                if duration < self.duration_threshold:
                    final_path = os.path.join(self.too_short_directory, os.path.basename(path))
                    if os.path.exists(path):
                        os.remove(path)
                    os.rename(temp_path, final_path)
                    logging.info(f"Moved and renamed {temp_path} to {final_path} due to short duration.")
                else:
                    final_path = os.path.join(self.base_directory, os.path.basename(path))
                    if os.path.exists(path):
                        os.remove(path)
                    os.rename(temp_path, final_path)
                    self.transcription_pool.submit(self.transcribe_and_move, final_path)
            except Exception as re_err:
                logging.error(f"Failed to re-process {path} after re-encoding: {str(re_err)}")
                self._handle_reencode_fail(path, temp_path)
        else:
            self._handle_reencode_fail(path, temp_path)

    def _handle_reencode_fail(self, path: str, temp_path: str) -> None:
        """
        If re-encoding fails, move the original file to too-short/error directory.
        """
        if os.path.exists(temp_path):
            os.remove(temp_path)
        original_dest_path = os.path.join(self.too_short_directory, os.path.basename(path))
        move_file(path, original_dest_path)
        logging.info(f"Moved original {path} to {original_dest_path} after repeated failures.")

    def _get_temp_path(self, original_path: str) -> str:
        """
        Generate a temporary file path in the too_short_directory with '_temp' suffix.
        """
        base, ext = os.path.splitext(original_path)
        temp_base = os.path.basename(base) + '_temp' + ext
        return os.path.join(self.too_short_directory, temp_base)

    def transcribe_and_move(self, path: str) -> None:
        """
        Transcribes the mp3 file and moves the mp3 and corresponding transcription
        into the talkgroup ID directory.
        """
        lock = self.file_locks.setdefault(path, threading.Lock())
        with lock:
            if not os.path.exists(path):
                logging.error(f"File not found, skipping transcription: {path}")
                return
            try:
                transcription_text = self.transcriber.transcribe_file(path)
                self.transcriber.save_transcription(path, transcription_text)
            except Exception as e:
                logging.error(f"Failed to transcribe {path}: {str(e)}")
            finally:
                # Clean up lock
                self.file_locks.pop(path, None)