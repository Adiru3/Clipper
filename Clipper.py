import time
import os
import threading
import cv2
import pyaudio
import pyautogui
import wave
import numpy as np
import sounddevice as sd
import sys
import tkinter as tk
from tkinter import messagebox
import json

print(sd.query_devices())

default_config = {
    "output_folder": "clips",
    "fps": 60,
    "clip_duration": 15,
    "system_audio_device": 14,
    "microphone_device": 13,
    "video_settings": {
        "resolution": [1920, 1080]
    },
    "audio_settings": {
        "chunk": 512,
        "format": 8,
        "channels": 2,
        "rate": 48000,
        "backend": "wasapi"
    },
    "microphone_settings": {
        "chunk": 512,
        "format": 8,
        "channels": 1,
        "rate": 48000,
        "backend": "wasapi"
    }
}

# Read configuration from JSON file
try:
    with open("config.json") as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    print("Config file not found. Using default configuration.")
    config = default_config
except json.JSONDecodeError as e:
    print(f"Error decoding JSON: {e}. Using default configuration.")
    config = default_config

# Use configuration settings
output_folder_path = config.get("output_folder", "default_output_folder")
fps = config.get("fps")
clip_duration = config.get("clip_duration")
system_audio_device = config.get("system_audio_device")
microphone_device = config.get("microphone_device")
audio_backend = config.get("audio_settings", {}).get("backend", "wasapi")
microphone_backend = config.get("microphone_settings", {}).get("backend", "wasapi")

# Define audio_settings and microphone_settings dictionaries
audio_settings = config.get("audio_settings", {})
microphone_settings = config.get("microphone_settings", {})

# Modify format in audio_settings
audio_settings["format"] = pyaudio.paInt24 if audio_settings.get("format") == 8 else audio_settings.get("format")
microphone_settings["format"] = pyaudio.paInt24 if microphone_settings.get("format") == 8 else microphone_settings.get("format")

# Use parameters from video_settings
video_settings = config.get("video_settings", {})
resolution = video_settings.get("resolution")


class VideoRecorder:
    def __init__(self, output_folder, clip_duration=10, fps=30, microphone_device=None):
        self.system_audio_duration = 0
        self.microphone_audio_duration = 0
        self.output_folder = output_folder
        self.clip_duration = clip_duration
        self.fps = fps
        self.terminate_event = threading.Event()
        self.recording_event = threading.Event()
        self.system_audio_frames = []
        self.microphone_audio_frames = []
        self.system_audio_device = config.get("system_audio_device")
        self.microphone_device = microphone_device
        self.clip_number = 1

        # Updated to read audio settings from config
        audio_settings = config.get("audio_settings", {})
        microphone_settings = config.get("microphone_settings", {})

        self.chunk = audio_settings.get("chunk")
        self.format = audio_settings.get("format")
        self.channels = audio_settings.get("channels")
        self.rate = audio_settings.get("rate")

        # Update settings from "microphone_settings"
        self.microphone_chunk = microphone_settings.get("chunk")
        self.microphone_format = microphone_settings.get("format")
        self.microphone_channels = microphone_settings.get("channels")
        self.microphone_rate = microphone_settings.get("rate")
        self.microphone_backend = microphone_settings.get("backend")

    def record_system_audio(self):
        start_time_system = time.time()
        FORMAT = self.format
        RATE = self.rate

        print("Recording system audio...")
        self.save_audio(
            self.system_audio_frames,
            f"system_audio_clip_{self.clip_number}.wav",
            self.channels,
            self.format,
            self.rate,
            duration=self.system_audio_duration
        )

        device_info = sd.query_devices(self.system_audio_device)
        print(device_info)
        channels = device_info['max_input_channels']

        def callback(indata, frames, time, status):
            nonlocal start_time_system
            if status:
                print(status, file=sys.stderr)
            if self.recording_event.is_set():
                self.system_audio_frames.append(indata.copy())

        with sd.InputStream(
                callback=callback, channels=channels, samplerate=RATE, device=self.system_audio_device
        ):
            self.terminate_event.wait()

        print("System audio recording complete.")

    def record_microphone_audio(self):
        start_time_microphone = time.time()
        CHUNK = self.microphone_chunk
        FORMAT = self.microphone_format
        CHANNELS = self.microphone_channels
        RATE = self.microphone_rate

        print("Recording microphone audio...")

        mic_info = sd.query_devices(self.microphone_device)
        mic_channels = mic_info['max_input_channels']  # Corrected line

        print("Microphone Info:", mic_info)

        def callback(indata, frames, time, status):
            nonlocal start_time_microphone
            if status:
                print(status, file=sys.stderr)
            if self.recording_event.is_set():
                self.microphone_audio_frames.append(indata.copy())

        with sd.InputStream(
                callback=callback, channels=self.microphone_channels, samplerate=RATE, device=self.microphone_device
        ):
            self.terminate_event.wait()

        self.microphone_audio_duration = time.time() - start_time_microphone

        print("Microphone audio recording complete.")
        self.save_audio(
            self.microphone_audio_frames,
            f"microphone_audio_clip_{self.clip_number}.wav",
            self.microphone_channels,
            self.microphone_format,
            self.microphone_rate,
            duration=self.microphone_audio_duration
        )

    def save_audio(self, audio_frames, filename, channels, format, rate, duration):
        audio_filename = os.path.join(self.output_folder, filename)
        # Ensure the directory exists
        os.makedirs(os.path.dirname(audio_filename), exist_ok=True)

        # Use sample width from configuration
        sample_width = (format + 7) // 8  # Calculate sample width in bytes

        wf = wave.open(audio_filename, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(b''.join(audio_frames))
        wf.close()

        # Calculate bitrate
        if duration != 0:
            file_size = os.path.getsize(audio_filename)
            bitrate = (8 * file_size) / duration  # in bits per second
            print(f"Bitrate for {filename}: {bitrate:.2f} bps")
        else:
            print(f"Error: Duration is zero for {filename}. Bitrate calculation skipped.")

    def record_clips(self):
        clip_number = 1
        while not self.terminate_event.is_set():
            start_time = time.time()
            clip_filename = os.path.join(self.output_folder, f"clip_{clip_number}.mp4")

            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            if resolution is not None and len(resolution) == 2:
                out = cv2.VideoWriter(clip_filename, fourcc, self.fps, tuple(resolution))
            else:
                # Use a default resolution (e.g., 1280x720) if resolution is not provided or invalid
                out = cv2.VideoWriter(clip_filename, fourcc, self.fps, (1920, 1080))

            self.recording_event.set()

            while time.time() - start_time < self.clip_duration:
                screen_img = pyautogui.screenshot()
                frame = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)
                out.write(frame)

            out.release()

            self.recording_event.clear()

            if os.path.getsize(clip_filename) > 0:
                system_audio_filename = os.path.join(self.output_folder, f"system_audio_clip_{clip_number}.wav")
                microphone_audio_filename = os.path.join(self.output_folder,
                                                         f"microphone_audio_clip_{clip_number}.wav")

                self.save_audio(self.system_audio_frames, system_audio_filename, self.channels, self.format,
                                self.rate, duration=self.system_audio_duration)
                self.save_audio(self.microphone_audio_frames, microphone_audio_filename, self.microphone_channels,
                                self.microphone_format, self.microphone_rate, duration=self.microphone_audio_duration)

            clip_number += 1

    def start_recording(self):
        self.terminate_event.clear()
        self.recording_event.clear()
        self.system_audio_frames = []
        self.microphone_audio_frames = []
        self.system_audio_thread = threading.Thread(target=self.record_system_audio)
        self.microphone_audio_thread = threading.Thread(target=self.record_microphone_audio)
        self.system_audio_thread.start()
        self.microphone_audio_thread.start()
        self.record_clips()

    def stop_recording(self):
        self.terminate_event.set()
        if self.system_audio_thread and self.system_audio_thread.is_alive():
            self.system_audio_thread.join()
        if self.microphone_audio_thread and self.microphone_audio_thread.is_alive():
            self.microphone_audio_thread.join()

            time.sleep(1)

        print("Recording stopped.")
        messagebox.showinfo("Recording Stopped", "Recording stopped successfully.")


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Clipper By Adiru")
        self.root.geometry("300x200")

        self.recorder = None
        self.microphone_device = config.get("microphone_device")  # Get the microphone device from the config

        self.start_button = tk.Button(root, text="Start Recording", command=self.start_recording)
        self.start_button.pack(pady=10)

        self.stop_button = tk.Button(root, text="Stop Recording", command=self.stop_recording, state=tk.DISABLED)
        self.stop_button.pack(pady=10)

        self.author_label = tk.Label(root, text="By Adiru")
        self.author_label.pack(pady=5)

        self.github_button = tk.Button(root, text="GitHub", command=self.open_github)
        self.github_button.pack(pady=5)

    def start_recording(self):
        if self.recorder is None:
            # Pass the microphone_device parameter when creating an instance of VideoRecorder
            self.recorder = VideoRecorder(output_folder_path, fps=fps, microphone_device=self.microphone_device)
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            threading.Thread(target=self.recorder.start_recording).start()

    def stop_recording(self):
        if self.recorder is not None:
            self.recorder.stop_recording()
            self.recorder = None
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

    def open_github(self):
        os.system("start https://github.com/Adiru3")


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
