import time
import os
import threading
import moviepy.editor as mp
import wave
import cv2
import pyaudio
import pyautogui
import numpy as np
import sounddevice as sd
import pygetwindow as gw
import sys
import tkinter as tk
from tkinter import messagebox
import json

# Read configuration from JSON file
try:
    with open("config.json") as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    print("Config file not found.")
except json.JSONDecodeError as e:
    print(f"Error decoding JSON: {e}")
    config = {}

# Use configuration settings
output_folder_path = config["output_folder"]

class VideoRecorder:
    def __init__(self, output_folder, clip_duration=10, fps=30):
        self.output_folder = output_folder
        self.clip_duration = clip_duration
        self.fps = fps
        self.terminate_event = threading.Event()
        self.recording_event = threading.Event()
        self.system_audio_frames = []
        self.microphone_audio_frames = []
        self.system_audio_device = config.get("system_audio_device", 9)
        self.microphone_device = config.get("microphone_device", 1)

    def record_system_audio(self):
        FORMAT = pyaudio.paInt16
        RATE = 44100

        print("Recording system audio...")

        def callback(indata, frames, time, status):
            if status:
                print(status, file=sys.stderr)
            if self.recording_event.is_set():
                self.system_audio_frames.append(indata.copy())

        with sd.InputStream(
                callback=callback, channels=None, samplerate=RATE, device=self.system_audio_device
        ):
            self.terminate_event.wait()

        print("System audio recording complete.")

    def record_microphone_audio(self):
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1  # Change this to 2 if your microphone is stereo
        RATE = 44100

        print("Recording microphone audio...")

        def callback(indata, frames, time, status):
            if status:
                print(status, file=sys.stderr)
            if self.recording_event.is_set():
                self.microphone_audio_frames.append(indata.copy())

        with sd.InputStream(
                callback=callback, channels=CHANNELS, samplerate=RATE, device=self.microphone_device
        ):
            self.terminate_event.wait()

        print("Microphone audio recording complete.")

    def save_audio(self, audio_frames, filename, channels, format, rate):
        audio_filename = os.path.join(self.output_folder, filename)
        wf = wave.open(audio_filename, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(pyaudio.PyAudio().get_sample_size(format))
        wf.setframerate(rate)
        wf.writeframes(b''.join(audio_frames))
        wf.close()

    def record_clips(self):
        clip_number = 1
        while not self.terminate_event.is_set():
            start_time = time.time()
            clip_filename = os.path.join(self.output_folder, f"clip_{clip_number}.mp4")

            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
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
                microphone_audio_filename = os.path.join(self.output_folder, f"microphone_audio_clip_{clip_number}.wav")

                # Check if the system audio file exists
                if os.path.exists(system_audio_filename):
                    video_clip = mp.VideoFileClip(clip_filename, fps=self.fps)
                    system_audio_clip = mp.AudioFileClip(system_audio_filename)
                    video_clip = video_clip.set_audio(system_audio_clip)
                    video_clip.write_videofile(clip_filename, codec="libx264", audio_codec="aac", fps=self.fps,
                                               audio_fps=44100)

                    # Save microphone audio separately
                    self.save_audio(
                        self.microphone_audio_frames, microphone_audio_filename,
                        channels=1, format=pyaudio.paInt16, rate=44100
                    )

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
            fps = 30  # Set the desired FPS for video recording
            self.recorder = VideoRecorder(output_folder_path, fps=fps)
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
