import RPi.GPIO as GPIO
from threading import Thread
import threading
from queue import Queue
import pyaudio
import wave
import time
import sounddevice as sd
import uuid
import os

print("Starting...")

global dial_pin
global hook_pin
global states
global start_recording
global playing_audio
global recording
global playback_all

dial_pin = 18
hook_pin = 16

playing_audio = False
start_recording = False
recording = False
playback_all = False

gpio_thread = None

lock = threading.Lock()

print("Setting up gpio...")
GPIO.setmode(GPIO.BOARD)
GPIO.setup(dial_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(hook_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

states = {"hook_free": 0, "dial_not_triggered": 0, "hook_state_changed": False}

def record_audio():
    global recording
    mic = pyaudio.PyAudio()
    stream = mic.open(format=pyaudio.paInt16, channels=1, rate=48000, input=True, frames_per_buffer=8192, input_device_index=1)
    stream.start_stream()
    data = stream.read(4096)
    frames = []

    while(recording):
        data = stream.read(4096)  
        frames.append(data)
        if(not states["hook_free"]):
            recording = False

    stream.stop_stream()
    stream.close()

    if not os.path.exists("audio"):
        os.makedirs("audio")

    with wave.open("audio/msg-" + str(uuid.uuid4()) + ".wav", 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(mic.get_sample_size(pyaudio.paInt16))
        wf.setframerate(48000)
        wf.writeframes(b''.join(frames))
        wf.close()

    mic.terminate()
    print("Recording finished\n")

def play_audio(audioPath):
    global playing_audio
    global start_recording
    device_id = 1
    chunk = 1024
    total_length = 0

    f = wave.open(audioPath,"rb")
    p = pyaudio.PyAudio()

    print("Opening device...")
    #open stream  
    stream = p.open(format = p.get_format_from_width(f.getsampwidth()),  
                    channels = f.getnchannels(),  
                    rate = f.getframerate(),  
                    output = True,
                    output_device_index=device_id)  
    #read data  

    data = f.readframes(chunk)  
    total_length = f.getnframes() / float(f.getframerate())

    end_early = False
    
    #play stream  
    while data:
        if(not states["hook_free"]):
            print("Ending audio early\n")
            end_early = True
            break
        stream.write(data)  
        data = f.readframes(chunk) 

    #stop stream  
    stream.stop_stream()  
    stream.close()  

    #close PyAudio
    p.terminate()

    playing_audio = False
    
    if(end_early):
        start_recording = False
        return
    ##t_end = time.time() + total_length
    ##while(time.time() < t_end):
     ##   if(not states["hook_free"]):
      ##      return
    
    print("Playback ended\n")
    start_recording = True
    #print("Recording should begin now", total_length)

def check_gpio():
    while True:
        new_d = GPIO.input(dial_pin)
        new_h = GPIO.input(hook_pin)

        if(new_d != states["dial_not_triggered"]):
            lock.acquire()
            states["dial_not_triggered"] = new_d
            lock.release()
            print("\nDial state changed")

        if(new_h != states["hook_free"]):
            lock.acquire()
            states["hook_free"] = new_h
            lock.release()
            states["hook_state_changed"] = True
            #print("\nHook state changed to ", new_h)

print("Starting gpio thread...")
gpio_thread = Thread(target=check_gpio)
gpio_thread.start()

print("Setup complete\n")

while True:
    if(states["hook_state_changed"]):
        states["hook_state_changed"] = False
        if(states["hook_free"]):
            playing_audio = True
            print("Playing audio")
            play_audio("intro-msg/pre-record.wav")

    if(states["hook_free"]):
        if(start_recording):
            print("Starting recording...")
            recording = True
            start_recording = False
            record_audio()
