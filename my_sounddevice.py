import json
import sounddevice as sd
import sys

# Redirect stdout to a text file with UTF-8 encoding and ignore errors
sys.stdout = open("my_sounddevice.txt", "w", encoding="utf-8", errors="ignore")

# Print available audio devices and their indices
info = sd.query_devices()
print("Available audio devices:")
for i, device in enumerate(info):
    try:
        print(f"{i}: {device['name']}")
    except UnicodeEncodeError:
        print(f"{i}: Unable to display device name due to encoding issues")

# You can manually set the indices based on the printed information.
# For example, if your desired system audio device is device index 0, and the microphone is device index 1: