# pyre-strict
import logging
import os
import signal
import sys
import argparse

from config import Config
from handler import MP3Handler

def signal_handler(sig: int, frame: object) -> None:
    logging.info('SIGINT or CTRL-C detected. Exiting gracefully.')
    sys.exit(0)

def start_monitoring(base_directory: str, too_short_directory: str) -> None:
    handler = MP3Handler(base_directory, too_short_directory)
    signal.signal(signal.SIGINT, signal_handler)
    handler.start()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SDR Trunk Transcriber")
    parser.add_argument("--root-directory", type=str, help="Path to the root directory containing MP3 files")
    parser.add_argument("--too-short-directory", type=str, help="Path to the directory for short/error files")

    args = parser.parse_args()

    # Determine directories with priority: CLI args > ENV VAR > Config default
    root_directory = args.root_directory or os.getenv("ROOT_DIRECTORY", Config.ROOT_DIRECTORY)
    too_short_directory = args.too_short_directory or os.getenv("TOO_SHORT_DIRECTORY", Config.TOO_SHORT_DIRECTORY)

    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename=Config.LOG_FILE_PATH,
        filemode='a'
    )

    start_monitoring(root_directory, too_short_directory)