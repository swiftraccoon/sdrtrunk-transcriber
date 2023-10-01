# sdrtrunk-transcriber
Python file for transcribing MP3 files from SDRTrunk recording capture. Built to be ran in a cronjob.

* `simplified_process.py` for those who just want transcriptions.
  * Should work out of the box for you.

* `process_recordings.py` for an example of what you could be doing.
  * not going to work out of the box. it uses custom data sources/databases.
----------------------------------------------

Example directory structure:

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

--------------------------------------------
Here is a website I built around this data (not included in this repo):

![Screenshot](https://github.com/swiftraccoon/sdrtrunk-transcriber/assets/47705353/d8611536-e7d8-4535-9502-0b511277ff4c)
