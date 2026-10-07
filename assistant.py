import speech_recognition as sr
import pyttsx3
import datetime
import webbrowser
import os
import sys
import threading
import time
import queue

ASSISTANT_NAME = "jarvis"
WAKE_WORDS = [ASSISTANT_NAME.lower()]

# Try to import pvporcupine and sounddevice for wake word detection
try:
    import pvporcupine
    import sounddevice as sd
    HAS_PV_PORCUPINE = True
except ImportError:
    HAS_PV_PORCUPINE = False

# Initialize Text-to-Speech Engine
engine = pyttsx3.init()
engine.setProperty('rate', 170)

def speak(text):
    """Convert text to speech"""
    print(f"{ASSISTANT_NAME}: {text}")
    engine.say(text)
    engine.runAndWait()

def listen():
    """Listen for audio input and return text"""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("\nListening...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source)
        try:
            command = recognizer.recognize_google(audio)
            print(f"You said: {command}")
            return command.lower()
        except sr.UnknownValueError:
            return ""
        except sr.RequestError:
            speak("Network error. Please check your connection.")
            return ""

def process_command(command):
    """Perform tasks based on user commands"""
    if "time" in command:
        now = datetime.datetime.now().strftime("%I:%M %p")
        speak(f"The current time is {now}")

    elif "open google" in command:
        speak("Opening Google")
        webbrowser.open("https://www.google.com")

    elif "open youtube" in command:
        speak("Opening YouTube")
        webbrowser.open("https://www.youtube.com")

    elif "search" in command:
        query = command.replace("search", "").strip()
        if query:
            speak(f"Searching for {query}")
            webbrowser.open(f"https://www.google.com/search?q={query}")

    elif "open notepad" in command:
        speak("Opening Notepad")
        if sys.platform == "win32":
            os.system("notepad.exe")
        elif sys.platform == "darwin":
            os.system("open -a TextEdit")

    elif "stop" in command or "exit" in command:
        speak("Goodbye!")
        sys.exit()

    else:
        speak("I am not programmed for that command yet.")

# Wake word detection using pvporcupine
class WakeWordDetector:
    def __init__(self, access_key=None, keywords=None, sensitivities=None):
        if not HAS_PV_PORCUPINE:
            raise ImportError("pvporcupine or sounddevice not available")
        
        if not access_key:
            access_key = os.environ.get('PICOVOICE_ACCESS_KEY')
            if not access_key:
                raise ValueError("PICOVOICE_ACCESS_KEY not set")
        
        if keywords is None:
            keywords = WAKE_WORDS
        self.keywords = keywords
        
        self.porcupine = pvporcupine.create(
            access_key=access_key,
            keywords=keywords,
            sensitivities=sensitivities or [0.5] * len(keywords)
        )
        self.sample_rate = self.porcupine.sample_rate
        self.frame_length = self.porcupine.frame_length
        self.audio_queue = queue.Queue()
        self.running = False
        self.wake_word_callback = None
        
    def audio_callback(self, indata, frames, time_info, status):
        if self.running:
            self.audio_queue.put(bytes(indata))
    
    def start_listening(self, wake_word_callback):
        """Start listening for wake word"""
        self.wake_word_callback = wake_word_callback
        self.running = True
        
        with sd.RawInputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='int16',
            blocksize=self.frame_length,
            callback=self.audio_callback
        ) as stream:
            print(f"Listening for wake word... (sample_rate={self.sample_rate}, frame_length={self.frame_length})")
            while self.running:
                audio_data = self.audio_queue.get()
                result = self.porcupine.process(audio_data)
                if result >= 0:
                    keyword = self.keywords[result] if result < len(self.keywords) else "wake word"
                    print(f"Wake word detected: {keyword}")
                    if self.wake_word_callback:
                        self.wake_word_callback()
    
    def stop_listening(self):
        self.running = False
    
    def cleanup(self):
        self.porcupine.delete()

# Fallback: Simple keyword detection using sounddevice + speech_recognition
def simple_wake_word_detection():
    """Simple wake word detection using sounddevice for audio capture"""
    recognizer = sr.Recognizer()
    print(f"\nSay '{ASSISTANT_NAME}' to activate...")
    
    # Record audio using sounddevice
    duration = 3
    sample_rate = 16000
    recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
    sd.wait()
    
    # Convert to speech_recognition AudioData
    audio_data = sr.AudioData(recording.tobytes(), sample_rate, 2)  # 2 bytes per sample for int16
    
    try:
        text = recognizer.recognize_google(audio_data).lower()
        print(f"Heard: {text}")
        if ASSISTANT_NAME.lower() in text:
            return True
    except sr.UnknownValueError:
        pass
    except sr.RequestError:
        print("Network error for speech recognition")
    return False

# Main Loop
if __name__ == "__main__":
    speak(f"Hello Boss! I am {ASSISTANT_NAME}. How can I help you?")
    
    # Try to use pvporcupine for wake word detection
    use_pvporcupine = False
    detector = None
    
    if HAS_PV_PORCUPINE:
        try:
            access_key = os.environ.get('PICOVOICE_ACCESS_KEY')
            if access_key:
                detector = WakeWordDetector(access_key=access_key)
                use_pvporcupine = True
                print("Using pvporcupine for wake word detection")
            else:
                print("PICOVOICE_ACCESS_KEY not set. Using simple wake word detection.")
        except Exception as e:
            print(f"Error initializing pvporcupine: {e}")
    
    if use_pvporcupine and detector:
        def on_wake_word():
            detector.stop_listening()
            time.sleep(0.2)
            speak("Yes?")
            command = listen()
            if command:
                process_command(command)
            if detector.running:
                detector.start_listening(on_wake_word)
        
        try:
            detector.start_listening(on_wake_word)
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            detector.cleanup()
    else:
        # Fallback to simple wake word detection
        print("Starting simple wake word detection loop...")
        while True:
            print("Waiting for wake word...")
            if simple_wake_word_detection():
                print("Wake word detected!")
                speak("Yes?")
                command = listen()
                if command:
                    process_command(command)