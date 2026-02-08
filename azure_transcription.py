import os
from pydub import AudioSegment
import azure.cognitiveservices.speech as speechsdk


def transcribe_mp3_to_text(mp3_path, azure_subscription_key, azure_region):
    # Convert MP3 to WAV
    audio = AudioSegment.from_mp3(mp3_path)
    wav_path = os.path.splitext(mp3_path)[0] + ".wav"
    audio.export(wav_path, format="wav")

    # Setup Azure Speech SDK
    speech_config = speechsdk.SpeechConfig(
        subscription=azure_subscription_key, region=azure_region
    )
    audio_input = speechsdk.AudioConfig(filename=wav_path)
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, audio_config=audio_input
    )

    # Transcribe
    result = speech_recognizer.recognize_once()

    # Clean up temporary WAV file
    os.remove(wav_path)

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text
    elif result.reason == speechsdk.ResultReason.NoMatch:
        return "No speech could be recognized"
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        return f"Speech Recognition canceled: {cancellation_details.reason}. {cancellation_details.error_details}"


# Usage
subscription_key = os.environ.get("AZURE_SUBSCRIPTION_KEY", "YOUR_AZURE_SUBSCRIPTION_KEY")
region = os.environ.get("AZURE_REGION", "YOUR_AZURE_REGION")
transcription = transcribe_mp3_to_text("path_to_your_file.mp3", subscription_key, region)
print(transcription)
