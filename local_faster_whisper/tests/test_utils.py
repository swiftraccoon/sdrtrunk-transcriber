import os
from unittest.mock import patch
from utils import extract_talkgroup_id, move_file

def test_extract_talkgroup_id():
    assert extract_talkgroup_id("somefile_TO_12345.mp3") == "12345"
    assert extract_talkgroup_id("somefile_TO_999_othersuffix.mp3") == "999"
    assert extract_talkgroup_id("no_talkgroup.mp3") == "unknown"

@patch("shutil.move")
@patch("os.makedirs")
def test_move_file(mock_makedirs, mock_move, tmp_path):
    src = tmp_path / "test.mp3"
    src.write_text("dummy")
    dst = tmp_path / "destination" / "test.mp3"
    move_file(str(src), str(dst))
    mock_makedirs.assert_called_once()
    mock_move.assert_called_once_with(str(src), str(dst))