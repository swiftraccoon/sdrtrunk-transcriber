from google.cloud import speech_v1p1beta1 as speech
from google.cloud.speech_v1p1beta1 import types
import io

def transcribe_audio_with_hints(gcs_uri, key_file, hints):
    """Transcribes the audio file stored in Google Cloud Storage using phrase hints."""
    client = speech.SpeechClient.from_service_account_json(key_file)

    audio = types.RecognitionAudio(uri=gcs_uri)
    config = types.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
        speech_contexts=[speech.SpeechContext(phrases=hints)]
    )

    response = client.recognize(config=config, audio=audio)

    # Combine the transcription results.
    transcription = ""
    for result in response.results:
        transcription += result.alternatives[0].transcript

    return transcription

# Usage example:
key_file_path = 'path_to_your_google_cloud_credentials.json'
audio_file_path = 'gs://your_bucket_name/your_audio_file.wav'  # Google Cloud Storage URI
phrase_hints = ["specific term1", "domain-specific term2", "another hint"]
transcription = transcribe_audio_with_hints(audio_file_path, key_file_path, phrase_hints)
print(transcription)