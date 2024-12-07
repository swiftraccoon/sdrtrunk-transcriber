# pyre-strict
from typing import Tuple

class Config:
    """
    Configuration parameters for the transcription monitoring service.
    Modify these as needed before running the program.
    """
    # Model and transcription parameters
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

    # File handling
    DURATION_THRESHOLD: float = 4.0
    DEBOUNCE_SECONDS: float = 1.0

    # Default directories (overridable by env vars or CLI)
    ROOT_DIRECTORY: str = "/home/USER/SDRTrunk/recordings"
    TOO_SHORT_DIRECTORY: str = "/home/USER/SDRTrunk/tooShortOrError"
    
    # Logging
    LOG_FILE_PATH: str = "uultra.log"
    LOG_LEVEL: str = "INFO"