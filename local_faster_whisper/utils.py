# pyre-strict
import os
import re
import shutil
import subprocess
from typing import Optional

def extract_talkgroup_id(filename: str) -> str:
    """
    Extracts the talkgroup ID from a filename using a regex pattern.
    If none is found, returns 'unknown'.
    """
    match = re.search(r"TO_(\d+)[._]", filename)
    return match.group(1) if match else "unknown"

def reencode_file(original_path: str, temp_path: str) -> bool:
    """
    Attempt to re-encode the file using ffmpeg.
    Returns True if successful, False otherwise.
    """
    try:
        subprocess.check_call(['ffmpeg', '-y', '-i', original_path, temp_path])
        return True
    except subprocess.CalledProcessError:
        return False

def move_file(src: str, dst: str) -> None:
    """
    Moves a file from src to dst, creating directories if needed.
    """
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(src, dst)