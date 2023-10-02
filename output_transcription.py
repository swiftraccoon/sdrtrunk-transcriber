import requests
import sys


def curl_transcribe_audio(file_path):
    # Define the endpoint and your API key
    url = "https://api.openai.com/v1/audio/transcriptions"
    api_key = "OPENAI_API_KEY"

    # Setup headers
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    # Open the file and setup files and data to be sent
    with open(file_path, "rb") as file:
        files = {
            "file": file,
        }
        data = {
            "model": "whisper-1",
            "prompt": "Transcribe the radio dispatch audio. The speaker is usually a dispatcher, police officer, or EMS responder. There are often callsigns, ten-codes, and addresses said.",
            "response_format": "json",
            "temperature": "0",
            "language": "en",
        }

        # Make the POST request
        response = requests.post(url, headers=headers, files=files, data=data)

    # Print the response or handle as needed
    return str(response.json())


def main():
    file = sys.argv[1]
    print(curl_transcribe_audio(file))


if __name__ == "__main__":
    main()
