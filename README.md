[![CodeFactor](https://www.codefactor.io/repository/github/swiftraccoon/sdrtrunk-transcriber/badge)](https://www.codefactor.io/repository/github/swiftraccoon/sdrtrunk-transcriber)

(started a C++ version: https://github.com/swiftraccoon/cpp-sdrtrunk-transcriber)

(released Node.JS website for displaying data: https://github.com/swiftraccoon/sdrtrunk-transcribed-web)
# SDRTrunk Transcriber
* `simplified_process.py` for those who just want transcriptions.
  * `email_simplified_process.py` with built-in gmail SMTP function

This script is designed to transcribe audio recordings using OpenAI's API and organize the recordings based on talkgroup IDs. It's perfect for users who have a directory full of audio recordings and need them to be transcribed and categorized systematically.

Features:

    Logging: Captures a detailed log of the operations including info, errors, and other relevant data, saved to script_log.log.
    Transcription Methods: Offers two methods to transcribe the audio files using OpenAI's API - directly through OpenAI's Python API and using a raw curl-like POST request.
    Automatic Organization: Automatically organizes the audio recordings by moving them into sub-directories based on their respective talkgroup IDs.
    Transcription Saving: After transcription, the script saves the text output to a .txt file with the same name as the source audio file.

How it Works:

    Sets up logging configurations.
    Defines constants like the directory where the recordings are located (RECORDINGS_DIR) and the OpenAI API key (OPENAI_API_KEY).
    Uses either the OpenAI Python API or a raw POST request method to transcribe the audio recordings.
    Processes each audio file:
        Checks if the file is an .mp3.
        Extracts the talkgroup ID from the file name.
        Moves the file to a sub-directory named after its talkgroup ID.
        Transcribes the audio.
        Saves the transcription to a .txt file.
    The main() function loops through all files in the specified directory and processes them.

How to Use:

    Replace YOUR_USER in the RECORDINGS_DIR path with the appropriate username.
    Replace YOUR_KEY_HERE in the OPENAI_API_KEY with your OpenAI API key.
    Ensure all .mp3 files you wish to process are in the specified RECORDINGS_DIR.
    Run the script.

Remember to keep your OpenAI API key secret and never expose it in public repositories. Always store such sensitive data securely.



---------------------------------------------------------
---------------------------------------------------------
---------------------------------------------------------



* `output_transcription.py` for those who want to pass a filename and get the output in terminal
  * `python output_transcription.py filename.mp3`

Features:

    Convenient Command-Line Usage: Just pass the audio file as a command-line argument, and the script does the rest.

    Focused Transcription Prompt: Uses a specific prompt to guide the transcription model to focus on the context of radio dispatch communication.

    OpenAI API Interaction:
        Utilizes the OpenAI API endpoint for audio transcriptions.
        Supports the "whisper-1" model.
        Custom headers for authorization.
        Requests are formatted specifically for audio content related to dispatch and emergency services.

    Output Format: The script prints the JSON response from the OpenAI API, making it easy to parse or further process if required.

How to Use:

    Replace OPENAI_API_KEY with your actual OpenAI API key.
    Run the script in the command line and pass the path of your audio file as an argument, like so:

    python script_name.py path_to_audio_file.mp3



---------------------------------------------------------
---------------------------------------------------------
---------------------------------------------------------



* `advanced_processing/process_recordings.py` for an example of what you could be doing.
  * not going to work out of the box. it uses custom data sources/databases.
 
This script is designed to process audio files by transcribing their content, extracting specific information, and then storing the results in an SQLite database.

    Logging & Configuration: Comprehensive logging setup captures all important operations, and configurations for directories and API keys are defined at the start.

    Radio ID Formatting: The script can format a radio ID by pairing it with a pre-defined name if available.

    Database Interaction:
        Connects to a SQLite database to store processed information.
        Can create new tables if they don't exist.
        Allows insertion of data into the database.

    Data Extraction:
        Extracts "ten codes" from transcriptions (specific codes used in law enforcement communication).
        Extracts specific signals and callsigns from transcriptions.
        Retrieves talkgroup names from an XML file.
        Determines radio ID directly from filenames.

    File Handling:
        Processes audio files by transcribing and formatting the transcription.
        Deletes audio files shorter than 9 seconds.
        Moves audio files to sub-directories based on their talkgroup IDs.
        Writes updated transcriptions to .txt files.

    Audio Transcription:
        Supports two methods to transcribe audio using OpenAI's API: Python API and raw POST requests.

    Data Loading:
        Loads "ten codes" and signals from predefined files.
        Loads callsigns from an SQLite database.

    Data Normalization:
        Normalizes specific patterns in transcriptions to aid in data extraction.
        Formats transcriptions by updating them with extracted ten codes, callsigns, and signals.

    Main Execution:
        Processes all audio recordings in a specified directory.
        Inserts processed data into the SQLite database.

----------------------------------------------

Example directory structure for `simplified_process.py` or `process_recordings.py`:

Processed recordings:
```
/home/YOUR_USER/SDRTrunk/recordings/52209
/home/YOUR_USER/SDRTrunk/recordings/52209/20230928_171201SOMEname-Control__TO_52209_FROM_2499908.mp3
/home/YOUR_USER/SDRTrunk/recordings/52209/20230928_171201SOMEname-Control__TO_52209_FROM_2499908.txt
/home/YOUR_USER/SDRTrunk/recordings/52209/20230928_175315SOMEname-Control__TO_52209_FROM_2152379.mp3
/home/YOUR_USER/SDRTrunk/recordings/52209/20230928_175315SOMEname-Control__TO_52209_FROM_2152379.txt
/home/YOUR_USER/SDRTrunk/recordings/52376
/home/YOUR_USER/SDRTrunk/recordings/52376/20230928_182227SOMEname-Control__TO_52376_FROM_1612755.mp3
/home/YOUR_USER/SDRTrunk/recordings/52376/20230928_182227SOMEname-Control__TO_52376_FROM_1612755.txt
/home/YOUR_USER/SDRTrunk/recordings/52376/20230928_182301SOMEname-Control__TO_52376_FROM_1612755.mp3
/home/YOUR_USER/SDRTrunk/recordings/52376/20230928_182301SOMEname-Control__TO_52376_FROM_1612755.txt
/home/YOUR_USER/SDRTrunk/recordings/41004
/home/YOUR_USER/SDRTrunk/recordings/41004/20230929_015445SOMEname-Control__TO_41004_FROM_1611142.mp3
/home/YOUR_USER/SDRTrunk/recordings/41004/20230929_015445SOMEname-Control__TO_41004_FROM_1611142.txt
```

Files to be processed:
```
/home/YOUR_USER/SDRTrunk/recordings/20231001_173024SOMEname-Control__TO_41003_FROM_1612266.mp3
/home/YOUR_USER/SDRTrunk/recordings/20231001_173110SOMEname-Control__TO_41003.mp3
/home/YOUR_USER/SDRTrunk/recordings/20231001_173127SOMEname-Control__TO_41003_FROM_1610051.mp3
/home/YOUR_USER/SDRTrunk/recordings/20231001_173133SOMEname-Control__TO_41003_FROM_1610051.mp3
```
