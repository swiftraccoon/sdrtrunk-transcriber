import json
import os
import pytest
from unittest.mock import MagicMock, patch
from transcriber import Transcriber

@pytest.fixture
def transcriber():
    with patch("faster_whisper.WhisperModel") as mock_model:
        mock_instance = MagicMock()
        # Mocking segments result
        mock_instance.transcribe.return_value = ([MagicMock(text="Hello"), MagicMock(text="World")], {})
        mock_model.return_value = mock_instance
        yield Transcriber()

def test_transcribe_file(transcriber):
    text = transcriber.transcribe_file("/fake/path.mp3")
    data = json.loads(text)
    assert "text" in data
    assert data["text"] == "Hello World"

def test_save_transcription(tmp_path, transcriber):
    # Mock extract_talkgroup_id to return a known ID
    with patch("utils.extract_talkgroup_id", return_value="1234"):
        test_path = os.path.join(str(tmp_path), "example_TO_1234.mp3")
        with open(test_path, "w") as f:
            f.write("fake data")

        transcription_text = json.dumps({"text": "Transcribed content"})
        transcriber.save_transcription(test_path, transcription_text)

        talkgroup_dir = os.path.join(str(tmp_path), "1234")
        assert os.path.exists(talkgroup_dir)

        txt_file = os.path.join(talkgroup_dir, "example_TO_1234.txt")
        assert os.path.exists(txt_file)
        assert open(txt_file).read() == "Transcribed content"

        mp3_file = os.path.join(talkgroup_dir, "example_TO_1234.mp3")
        assert os.path.exists(mp3_file)