#!/usr/bin/env python3

"""
Audio Recording and Image Generation Script

Records audio from microphone, sends it to the Azure Functions API,
and saves the generated 360° panorama image.

Usage:
    python3 record-and-generate.py

Controls:
    Press ENTER to start recording
    Press ENTER again to stop recording
"""

import sys
import os
import time
import wave
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
import threading
import requests
from datetime import datetime
from pathlib import Path

# Try to import sounddevice, provide helpful error if not installed
try:
    import sounddevice as sd
    import numpy as np
except ImportError:
    print("❌ Required packages not installed!")
    print("")
    print("Install with:")
    print("  pip3 install sounddevice numpy")
    print("")
    print("Or if you prefer pyaudio:")
    print("  brew install portaudio")
    print("  pip3 install pyaudio")
    sys.exit(1)

# Configuration
API_URL = os.getenv("AZURE_FUNCTION_URL", "https://endpoint-gtfbdtb7bwf2hsfb.canadacentral-01.azurewebsites.net/api/audio-to-image")
FUNCTION_CODE = os.getenv("AZURE_FUNCTION_CODE", "")
if FUNCTION_CODE:
    API_URL = f"{API_URL}?code={FUNCTION_CODE}"
SAMPLE_RATE = 16000  # Azure Speech Service works best with 16kHz
CHANNELS = 1  # Mono audio
RESULTS_DIR = Path(__file__).parent / "results"
TEMP_DIR = Path(__file__).parent / "temp"

def setup_directories():
    """Create results and temp directories if they don't exist"""
    RESULTS_DIR.mkdir(exist_ok=True)
    TEMP_DIR.mkdir(exist_ok=True)
    print(f"📁 Results will be saved to: {RESULTS_DIR.absolute()}")
    print("")

def record_audio():
    """Record audio from the microphone until Enter is pressed"""
    print("🎤 Press ENTER to start recording...")
    input()
    
    print("   🔴 RECORDING - Press ENTER to stop")
    print("")
    
    # Use a list to collect audio chunks (mutable for callback)
    audio_chunks = []
    stop_recording = threading.Event()
    
    def audio_callback(indata, frames, time_info, status):
        """Callback to capture audio data"""
        if status:
            print(f"   ⚠️  {status}")
        audio_chunks.append(indata.copy())
    
    # Start recording in a stream
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype='int16',
        callback=audio_callback
    ):
        # Wait for Enter key in main thread
        input()
        stop_recording.set()
    
    # Combine all audio chunks
    if audio_chunks:
        recording = np.concatenate(audio_chunks, axis=0)
    else:
        recording = np.array([], dtype='int16')
    
    duration = len(recording) / SAMPLE_RATE
    print(f"   ✅ Recording complete! ({duration:.1f} seconds)")
    print("")
    
    return recording

def save_wav(recording, filename):
    """Save recording as WAV file"""
    with wave.open(str(filename), 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(recording.tobytes())
    
    print(f"💾 Audio saved to: {filename}")

def send_to_api(audio_file):
    """Send audio file to the API and get the generated image"""
    print("")
    print("📤 Sending audio to Azure Functions API...")
    print(f"   Endpoint: {API_URL}")
    print("")
    
    try:
        with open(audio_file, 'rb') as f:
            headers = {'Content-Type': 'audio/wav'}
            
            print("⏳ Generating 360° panorama...")
            print("   This may take 3-5 minutes (includes upscaling)")
            print("")
            
            response = requests.post(
                API_URL,
                data=f,
                headers=headers,
                timeout=900  # 15 minutes timeout
            )
        
        if response.status_code == 200:
            # Extract metadata from headers
            transcription = response.headers.get('X-Original-Transcription', '')
            prompt = response.headers.get('X-Enhanced-Prompt', '')
            
            # Decode base64 if present
            if transcription:
                import base64
                transcription = base64.b64decode(transcription).decode('utf-8')
                print(f"📝 Transcription: {transcription}")
            
            if prompt:
                import base64
                prompt = base64.b64decode(prompt).decode('utf-8')
                print(f"✨ Enhanced Prompt: {prompt}")
            
            print("")
            return response.content, transcription, prompt
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"   {response.text}")
            return None, None, None
    
    except requests.exceptions.Timeout:
        print("❌ Request timed out! The generation took too long.")
        print("   The API might still be processing. Check the API terminal.")
        return None, None, None
    
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API!")
        print("   Make sure the API is running in another terminal:")
        print("   ./start-api.sh")
        return None, None, None
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None, None

def save_image(image_data, transcription=""):
    """Save the generated image with timestamp"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create a safe filename from transcription
    safe_name = ""
    if transcription:
        safe_name = "".join(c for c in transcription[:30] if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_')
        safe_name = f"_{safe_name}"
    
    filename = RESULTS_DIR / f"panorama_{timestamp}{safe_name}.png"
    
    with open(filename, 'wb') as f:
        f.write(image_data)
    
    print(f"🖼️  Image saved: {filename}")
    print(f"   Size: {len(image_data) / 1024 / 1024:.2f} MB")
    
    return filename

def save_metadata(filename, transcription, prompt):
    """Save metadata as a text file"""
    metadata_file = filename.with_suffix('.txt')
    
    with open(metadata_file, 'w') as f:
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"\n")
        f.write(f"Original Transcription:\n")
        f.write(f"{transcription}\n")
        f.write(f"\n")
        f.write(f"Enhanced Prompt:\n")
        f.write(f"{prompt}\n")
    
    print(f"📄 Metadata saved: {metadata_file}")

def main():
    """Main function"""
    print("")
    print("🎨 Audio to 360° Panorama Generator")
    print("=" * 60)
    print("")
    
    # Setup
    setup_directories()
    
    # Check if API is accessible
    try:
        response = requests.get("https://endpoint-gtfbdtb7bwf2hsfb.canadacentral-01.azurewebsites.net", timeout=5)
        print("✅ Azure API is accessible")
        print("")
    except:
        print("⚠️  Warning: Cannot connect to Azure Function App")
        print("   The API might be temporarily unavailable")
        print("")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
        print("")
    
    # Record audio (press Enter to start/stop)
    recording = record_audio()
    
    # Save temporary WAV file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_wav = TEMP_DIR / f"recording_{timestamp}.wav"
    save_wav(recording, temp_wav)
    
    # Send to API
    image_data, transcription, prompt = send_to_api(temp_wav)
    
    if image_data:
        # Save image
        image_file = save_image(image_data, transcription)
        
        # Save metadata
        if transcription and prompt:
            save_metadata(image_file, transcription, prompt)
        
        print("")
        print("=" * 60)
        print("✅ SUCCESS! Your 360° panorama is ready!")
        print("=" * 60)
        print("")
        print(f"📂 Open folder: open {RESULTS_DIR.absolute()}")
        print(f"🖼️  Open image:  open {image_file.absolute()}")
        print("")
    else:
        print("")
        print("=" * 60)
        print("❌ Failed to generate image")
        print("=" * 60)
        print("")
        sys.exit(1)
    
    # Cleanup temp file
    try:
        temp_wav.unlink()
    except:
        pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("")
        print("")
        print("⚠️  Interrupted by user")
        sys.exit(1)
