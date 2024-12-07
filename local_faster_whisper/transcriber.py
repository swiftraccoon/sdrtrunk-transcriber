# pyre-strict
import json
import logging
import os
from typing import List, Any

from config import Config
from utils import extract_talkgroup_id

# pyre-ignore[21]: No type hints from 3rd party library
import faster_whisper

class Transcriber:
    """
    Handles transcription using the faster_whisper model.
    """
    def __init__(self) -> None:
        self.model = faster_whisper.WhisperModel(
            Config.MODEL_SIZE, device="cuda"
        )

    def transcribe_file(self, path: str) -> str:
        """
        Transcribe the given mp3 file and return the transcribed text.
        Raises an exception on failure.
        """
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
            initial_prompt="",
            temperature=Config.TEMPERATURE,
            vad_filter=True,
            vad_parameters={
                "threshold": Config.THRESHOLD,
                "min_silence_duration_ms": Config.MIN_SILENCE_DURATION_MS,
                "window_size_samples": Config.WINDOW_SIZE_SAMPLES,
            },
            language=Config.LANGUAGE
        )
        return self._format_segments(segments)

    def _format_segments(self, segments: List[Any]) -> str:
        formatted_segments = [{"text": segment.text} for segment in segments]
        formatted_text = " ".join(s["text"].strip() for s in formatted_segments)
        # Return JSON with a 'text' field
        return json.dumps({"text": formatted_text})

    def save_transcription(self, path: str, transcription_text: str) -> None:
        """
        Saves the transcription text into a corresponding .txt file
        in a directory based on the talkgroup ID extracted from filename.
        """
        talkgroup_id = extract_talkgroup_id(os.path.basename(path))
        final_directory = os.path.join(os.path.dirname(path), talkgroup_id)
        os.makedirs(final_directory, exist_ok=True)

        base_filename = os.path.splitext(os.path.basename(path))[0]
        transcription_path = os.path.join(final_directory, base_filename + ".txt")

        # Load JSON to extract the final text from the 'text' field
        text_data = json.loads(transcription_text)['text']
        with open(transcription_path, 'w', encoding='utf-8') as f:
            f.write(text_data)

        # Move the MP3 file into the same directory
        final_mp3_path = os.path.join(final_directory, os.path.basename(path))
        os.replace(path, final_mp3_path)
        logging.info(f"Transcribed and moved {path} to {final_directory}")