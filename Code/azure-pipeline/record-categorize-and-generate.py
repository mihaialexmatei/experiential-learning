#!/usr/bin/env python3

"""
Audio Recording and Image Generation Script with Category Upload

Records audio from microphone, sends it to the Azure Functions API,
saves the generated 360° panorama image locally, and uploads it to Azure Blob Storage
in a specific category.

Usage:
    python3 record-categorize-and-generate.py

Controls:
    Select category first (beach, mountain, forest, garden)
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

# Try to import required packages
try:
    import sounddevice as sd
    import numpy as np
except ImportError:
    print("❌ Required packages not installed!")
    print("")
    print("Install with:")
    print("  pip3 install sounddevice numpy")
    sys.exit(1)

try:
    from azure.storage.blob import BlobServiceClient
except ImportError:
    print("❌ Azure Storage SDK not installed!")
    print("")
    print("Install with:")
    print("  pip3 install azure-storage-blob")
    sys.exit(1)

# Configuration - HARDCODED FOR PORTABILITY (works on any PC without env vars)
API_BASE = "https://endpoint-gtfbdtb7bwf2hsfb.westeurope-01.azurewebsites.net/api"
FUNCTION_KEY = "3LKq6SmNriNUNQ6tXeSsE3JqGRKOj58YypNp5RDWhZ7-AzFu3Cr5Fg=="

def get_api_url(endpoint):
    """Build full API URL with function code"""
    url = f"{API_BASE}/{endpoint}"
    if FUNCTION_KEY:
        url = f"{url}?code={FUNCTION_KEY}"
    return url

STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "premade-scenes")

SAMPLE_RATE = 16000  # Azure Speech Service works best with 16kHz
CHANNELS = 1  # Mono audio
PANORAMA_OUTPUT_DIR = Path(__file__).parent / "dotnet-functions" / "panorama_output"
TEMP_DIR = Path(__file__).parent / "temp"

# Valid categories
VALID_CATEGORIES = ["beach", "mountain", "forest", "garden"]

def setup_directories():
    """Create panorama_output and temp directories if they don't exist"""
    PANORAMA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(exist_ok=True)
    print(f"📁 Images will be saved to: {PANORAMA_OUTPUT_DIR.absolute()}")
    print("")

def select_category():
    """Prompt user to select a category"""
    print("📂 Available Categories:")
    print("")
    for i, category in enumerate(VALID_CATEGORIES, 1):
        print(f"  {i}. {category.capitalize()}")
    print("")
    
    while True:
        try:
            choice = input("Select category (1-4 or name): ").strip().lower()
            
            # Check if it's a number
            if choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(VALID_CATEGORIES):
                    category = VALID_CATEGORIES[index]
                    print(f"✅ Selected: {category.capitalize()}")
                    print("")
                    return category
            
            # Check if it's a category name
            if choice in VALID_CATEGORIES:
                print(f"✅ Selected: {choice.capitalize()}")
                print("")
                return choice
            
            print(f"❌ Invalid selection. Please choose 1-4 or enter: {', '.join(VALID_CATEGORIES)}")
            print("")
        except KeyboardInterrupt:
            print("\n\n⚠️  Cancelled by user")
            sys.exit(1)
        except:
            print("❌ Invalid input. Please try again.")
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
    api_url = get_api_url("audio-to-image")
    print("")
    print("📤 Sending audio to Azure Functions API...")
    print(f"   Endpoint: {api_url[:70]}...")
    print("")
    
    try:
        with open(audio_file, 'rb') as f:
            headers = {'Content-Type': 'audio/wav'}
            
            print("⏳ Generating 360° panorama...")
            print("   This may take 3-5 minutes (includes upscaling)")
            print("")
            
            response = requests.post(
                api_url,
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

def save_image_locally(image_data, category, transcription=""):
    """Save the generated image locally with timestamp and category"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create a safe filename from transcription
    safe_name = ""
    if transcription:
        safe_name = "".join(c for c in transcription[:30] if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_')
        safe_name = f"_{safe_name}"
    
    filename = PANORAMA_OUTPUT_DIR / f"{category}_panorama_{timestamp}{safe_name}.png"
    
    with open(filename, 'wb') as f:
        f.write(image_data)
    
    print(f"🖼️  Image saved locally: {filename}")
    print(f"   Size: {len(image_data) / 1024 / 1024:.2f} MB")
    
    return filename

def upload_to_blob_storage(image_data, category, transcription=""):
    """Upload the generated image to Azure Blob Storage with category prefix"""
    if not STORAGE_CONNECTION_STRING:
        print("⚠️  Warning: AZURE_STORAGE_CONNECTION_STRING not set in .env")
        print("   Skipping blob upload")
        return None
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create blob name with category prefix
        safe_name = ""
        if transcription:
            safe_name = "".join(c for c in transcription[:30] if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_name = safe_name.replace(' ', '_')
            safe_name = f"_{safe_name}"
        
        blob_name = f"{category}_panorama_{timestamp}{safe_name}.png"
        
        # Create blob service client
        blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
        
        # Get container client (create container if it doesn't exist)
        container_client = blob_service_client.get_container_client(STORAGE_CONTAINER_NAME)
        try:
            container_client.get_container_properties()
        except:
            print(f"📦 Creating container: {STORAGE_CONTAINER_NAME}")
            container_client.create_container()
        
        # Upload blob
        blob_client = container_client.get_blob_client(blob_name)
        
        print(f"☁️  Uploading to Azure Blob Storage...")
        blob_client.upload_blob(image_data, overwrite=True)
        
        blob_url = blob_client.url
        print(f"✅ Uploaded to blob: {blob_name}")
        print(f"   URL: {blob_url}")
        
        return blob_url
    
    except Exception as e:
        print(f"❌ Failed to upload to blob storage: {e}")
        return None

def save_metadata(filename, category, transcription, prompt, blob_url=None):
    """Save metadata as a text file"""
    metadata_file = filename.with_suffix('.txt')
    
    with open(metadata_file, 'w') as f:
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Category: {category.capitalize()}\n")
        f.write(f"\n")
        f.write(f"Original Transcription:\n")
        f.write(f"{transcription}\n")
        f.write(f"\n")
        f.write(f"Enhanced Prompt:\n")
        f.write(f"{prompt}\n")
        if blob_url:
            f.write(f"\n")
            f.write(f"Blob Storage URL:\n")
            f.write(f"{blob_url}\n")
    
    print(f"📄 Metadata saved: {metadata_file}")

def main():
    """Main function"""
    print("")
    print("🎨 Audio to 360° Panorama Generator with Category Upload")
    print("=" * 60)
    print("")
    
    # Setup
    setup_directories()
    
    # Step 1: Select category BEFORE recording
    category = select_category()
    
    # Check if API is accessible
    try:
        response = requests.get("https://endpoint-gtfbdtb7bwf2hsfb.westeurope-01.azurewebsites.net", timeout=5)
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
    
    # Step 2: Record audio (press Enter to start/stop)
    recording = record_audio()
    
    # Step 3: Save temporary WAV file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_wav = TEMP_DIR / f"recording_{timestamp}.wav"
    save_wav(recording, temp_wav)
    
    # Step 4: Send to API
    image_data, transcription, prompt = send_to_api(temp_wav)
    
    if image_data:
        # Step 5: Save image locally
        image_file = save_image_locally(image_data, category, transcription)
        
        # Step 6: Upload to blob storage
        blob_url = upload_to_blob_storage(image_data, category, transcription)
        
        # Step 7: Save metadata
        if transcription and prompt:
            save_metadata(image_file, category, transcription, prompt, blob_url)
        
        print("")
        print("=" * 60)
        print("✅ SUCCESS! Your 360° panorama is ready!")
        print("=" * 60)
        print("")
        print(f"📂 Open folder: open {PANORAMA_OUTPUT_DIR.absolute()}")
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
