#!/usr/bin/env python3

"""
Standalone Azure Panorama Generator Test Script

This script can be run from any computer to test the Azure pipeline.
It records audio, sends it to the Azure Function, and saves the generated panorama.

Requirements:
    pip3 install sounddevice numpy requests

Usage:
    python3 test-from-anywhere.py

Controls:
    Press ENTER to start recording
    Press ENTER again to stop recording
"""

import sys
import os
import time
import wave
import threading
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from pathlib import Path

# Try to import required packages
try:
    import sounddevice as sd
    import numpy as np
    import requests
except ImportError:
    print("❌ Required packages not installed!")
    print("")
    print("Install with:")
    print("  pip3 install sounddevice numpy requests")
    print("")
    sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================
API_URL = os.getenv("AZURE_FUNCTION_URL", "https://endpoint-gtfbdtb7bwf2hsfb.canadacentral-01.azurewebsites.net/api/audio-to-image")
FUNCTION_CODE = os.getenv("AZURE_FUNCTION_CODE", "")
if FUNCTION_CODE:
    API_URL = f"{API_URL}?code={FUNCTION_CODE}"
SAMPLE_RATE = 16000  # Azure Speech Service works best with 16kHz
CHANNELS = 1  # Mono audio
# ============================================================================

def record_audio():
    """Record audio from the microphone until Enter is pressed"""
    print("")
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
    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype='int16',
            callback=audio_callback
        ):
            # Wait for Enter key in main thread
            input()
            stop_recording.set()
    except Exception as e:
        print(f"❌ Recording error: {e}")
        print("")
        print("Troubleshooting:")
        print("  - Check that your microphone is connected")
        print("  - Grant microphone permissions to Terminal/Python")
        print("  - Try: python3 -m sounddevice")
        sys.exit(1)
    
    # Combine all audio chunks
    if audio_chunks:
        recording = np.concatenate(audio_chunks, axis=0)
    else:
        recording = np.array([], dtype='int16')
    
    duration = len(recording) / SAMPLE_RATE
    print(f"   ✅ Recording complete! ({duration:.1f} seconds)")
    print("")
    
    if duration < 1:
        print("⚠️  Warning: Recording is very short (less than 1 second)")
        print("")
    
    return recording

def save_wav_to_memory(recording):
    """Save recording as WAV bytes in memory"""
    import io
    
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(recording.tobytes())
    
    buffer.seek(0)
    return buffer.read()

def send_to_api(audio_bytes):
    """Send audio to the Azure API and get the generated image"""
    print("📤 Sending audio to Azure Functions API...")
    print(f"   Endpoint: {API_URL[:60]}...")
    print("")
    
    try:
        headers = {'Content-Type': 'audio/wav'}
        
        print("⏳ Processing your request...")
        print("   1. Transcribing speech to text")
        print("   2. Enhancing prompt with AI")
        print("   3. Generating 360° panorama")
        print("   4. Upscaling to high resolution")
        print("")
        print("   This may take 3-5 minutes...")
        print("")
        
        response = requests.post(
            API_URL,
            data=audio_bytes,
            headers=headers,
            timeout=900  # 15 minutes timeout
        )
        
        if response.status_code == 200:
            # Extract metadata from headers
            transcription = ""
            prompt = ""
            
            try:
                import base64
                if 'X-Original-Transcription' in response.headers:
                    transcription = base64.b64decode(response.headers['X-Original-Transcription']).decode('utf-8')
                    print(f"📝 Transcription: {transcription}")
                
                if 'X-Enhanced-Prompt' in response.headers:
                    prompt = base64.b64decode(response.headers['X-Enhanced-Prompt']).decode('utf-8')
                    print(f"✨ Enhanced Prompt: {prompt}")
                
                print("")
            except:
                pass
            
            return response.content, transcription, prompt
        else:
            print(f"❌ API Error: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   {error_data.get('error', response.text)}")
            except:
                print(f"   {response.text}")
            return None, None, None
    
    except requests.exceptions.Timeout:
        print("❌ Request timed out!")
        print("   The generation took longer than expected.")
        return None, None, None
    
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Azure API!")
        print("   Check your internet connection.")
        return None, None, None
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None, None

def save_results(image_data, transcription="", prompt=""):
    """Save the generated image and metadata"""
    # Create output directory
    output_dir = Path.cwd() / "panorama_output"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save image
    image_file = output_dir / f"panorama_{timestamp}.png"
    with open(image_file, 'wb') as f:
        f.write(image_data)
    
    print(f"🖼️  Image saved: {image_file}")
    print(f"   Size: {len(image_data) / 1024 / 1024:.2f} MB")
    
    # Save metadata
    if transcription or prompt:
        metadata_file = output_dir / f"panorama_{timestamp}.txt"
        with open(metadata_file, 'w') as f:
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"\n")
            if transcription:
                f.write(f"Original Transcription:\n")
                f.write(f"{transcription}\n")
                f.write(f"\n")
            if prompt:
                f.write(f"Enhanced Prompt:\n")
                f.write(f"{prompt}\n")
        
        print(f"📄 Metadata saved: {metadata_file}")
    
    return image_file, output_dir

def main():
    """Main function"""
    print("")
    print("=" * 70)
    print("🎨 Azure 360° Panorama Generator - Test Script")
    print("=" * 70)
    print("")
    print("This script will:")
    print("  1. Record your voice describing a landscape")
    print("  2. Send it to Azure for processing")
    print("  3. Generate a 360° panorama image")
    print("")
    
    # Test API connectivity
    print("🔍 Testing Azure API connectivity...")
    try:
        test_response = requests.get(
            "https://endpoint-gtfbdtb7bwf2hsfb.canadacentral-01.azurewebsites.net",
            timeout=10
        )
        print("✅ Azure API is accessible")
    except Exception as e:
        print(f"⚠️  Warning: Cannot reach Azure API ({e})")
        print("")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    print("")
    print("=" * 70)
    
    # Record audio
    recording = record_audio()
    
    # Check if recording has data
    if len(recording) == 0:
        print("❌ No audio recorded!")
        sys.exit(1)
    
    # Convert to WAV bytes
    audio_bytes = save_wav_to_memory(recording)
    
    # Send to API
    image_data, transcription, prompt = send_to_api(audio_bytes)
    
    if image_data:
        # Save results
        image_file, output_dir = save_results(image_data, transcription, prompt)
        
        print("")
        print("=" * 70)
        print("✅ SUCCESS! Your 360° panorama is ready!")
        print("=" * 70)
        print("")
        print(f"📂 Output folder: {output_dir.absolute()}")
        print(f"🖼️  Image file:    {image_file.name}")
        print("")
        print("To view the image:")
        print(f"  open {image_file}")
        print("")
    else:
        print("")
        print("=" * 70)
        print("❌ Failed to generate panorama")
        print("=" * 70)
        print("")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("")
        print("")
        print("⚠️  Interrupted by user")
        sys.exit(1)
