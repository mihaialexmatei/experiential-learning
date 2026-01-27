#!/usr/bin/env python3

"""
Standalone Azure Panorama Generator Test Script

This script can be run from ANY computer to test the Azure pipeline.
No environment variables needed - all configuration is hardcoded.

It records audio, sends it to the Azure Function, and saves the generated panorama.

Requirements:
    pip3 install sounddevice numpy requests

Usage:
    python3 test-from-anywhere.py              # Generate image only (original mode)
    python3 test-from-anywhere.py --with-sound # Generate image AND get matching sound
    python3 test-from-anywhere.py --sound-only # Get a random sound for a category

Controls:
    Press ENTER to start recording
    Press ENTER again to stop recording

Unity Integration URLs (no authentication needed for Anonymous endpoints):
    GET  /api/sounds/{category}  - Get random sound (beach, mountain, forest, garden)
    GET  /api/images/{category}  - Get random image (beach, mountain, forest, garden)
    POST /api/audio-to-image-with-sound - Send audio, get image + sound JSON (requires key)
"""

import sys
import os
import time
import wave
import threading
import argparse
import json
import base64
from datetime import datetime
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
# CONFIGURATION - HARDCODED FOR PORTABILITY (works on any PC without env vars)
# ============================================================================
# Azure Function App base URL
API_BASE = "https://endpoint-gtfbdtb7bwf2hsfb.westeurope-01.azurewebsites.net/api"

# Host-level function key (works for ALL functions)
FUNCTION_KEY = "daWi0Itt20SAgEJ5H6j63j9RNPtMXxxJ-Q3e8ZgddrkVAzFuI7bfxg=="

# Audio settings
SAMPLE_RATE = 16000  # Azure Speech Service works best with 16kHz
CHANNELS = 1  # Mono audio

# Valid scene categories
VALID_CATEGORIES = ["beach", "mountain", "forest", "garden"]
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

def get_api_url(endpoint):
    """Build full API URL with function code"""
    url = f"{API_BASE}/{endpoint}"
    if FUNCTION_KEY:
        url = f"{url}?code={FUNCTION_KEY}"
    return url

def send_to_api_image_only(audio_bytes):
    """Send audio to the Azure API and get the generated image (no sound)"""
    api_url = get_api_url("audio-to-image")
    print("📤 Sending audio to Azure Functions API...")
    print(f"   Endpoint: {api_url[:70]}...")
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
            api_url,
            data=audio_bytes,
            headers=headers,
            timeout=900  # 15 minutes timeout
        )
        
        if response.status_code == 200:
            # Extract metadata from headers
            transcription = ""
            prompt = ""
            
            try:
                if 'X-Original-Transcription' in response.headers:
                    transcription = base64.b64decode(response.headers['X-Original-Transcription']).decode('utf-8')
                    print(f"📝 Transcription: {transcription}")
                
                if 'X-Enhanced-Prompt' in response.headers:
                    prompt = base64.b64decode(response.headers['X-Enhanced-Prompt']).decode('utf-8')
                    print(f"✨ Enhanced Prompt: {prompt}")
                
                print("")
            except:
                pass
            
            return {
                'image': response.content,
                'transcription': transcription,
                'prompt': prompt,
                'category': None,
                'sound': None,
                'sound_name': None
            }
        else:
            print(f"❌ API Error: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   {error_data.get('error', response.text)}")
            except:
                print(f"   {response.text}")
            return None
    
    except requests.exceptions.Timeout:
        print("❌ Request timed out!")
        print("   The generation took longer than expected.")
        return None
    
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Azure API!")
        print("   Check your internet connection.")
        return None
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def send_to_api_with_sound(audio_bytes):
    """Send audio to the Azure API and get both image AND sound"""
    api_url = get_api_url("audio-to-image-with-sound")
    print("📤 Sending audio to Azure Functions API (with sound)...")
    print(f"   Endpoint: {api_url[:70]}...")
    print("")
    
    try:
        headers = {'Content-Type': 'audio/wav'}
        
        print("⏳ Processing your request...")
        print("   1. Transcribing speech to text")
        print("   2. Enhancing prompt with AI")
        print("   3. Generating 360° panorama")
        print("   4. Categorizing scene")
        print("   5. Fetching matching ambient sound")
        print("")
        print("   This may take 3-5 minutes...")
        print("")
        
        response = requests.post(
            api_url,
            data=audio_bytes,
            headers=headers,
            timeout=900  # 15 minutes timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('success'):
                print(f"📝 Transcription: {data.get('originalTranscription', 'N/A')}")
                print(f"✨ Enhanced Prompt: {data.get('enhancedPrompt', 'N/A')[:100]}...")
                print(f"🏷️  Category: {data.get('category', 'N/A')}")
                if data.get('soundName'):
                    print(f"🎵 Sound: {data.get('soundName')}")
                print("")
                
                return {
                    'image': base64.b64decode(data['image']) if data.get('image') else None,
                    'transcription': data.get('originalTranscription', ''),
                    'prompt': data.get('enhancedPrompt', ''),
                    'category': data.get('category'),
                    'sound': base64.b64decode(data['sound']) if data.get('sound') else None,
                    'sound_name': data.get('soundName')
                }
            else:
                print(f"❌ API Error: {data.get('error', 'Unknown error')}")
                return None
        else:
            print(f"❌ API Error: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   {error_data.get('error', response.text)}")
            except:
                print(f"   {response.text}")
            return None
    
    except requests.exceptions.Timeout:
        print("❌ Request timed out!")
        print("   The generation took longer than expected.")
        return None
    
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Azure API!")
        print("   Check your internet connection.")
        return None
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def get_random_sound(category):
    """Get a random ambient sound for a category"""
    api_url = get_api_url(f"sounds/{category}")
    print(f"🎵 Getting random sound for category: {category}")
    print(f"   Endpoint: {api_url[:70]}...")
    print("")
    
    try:
        response = requests.get(api_url, timeout=30)
        
        if response.status_code == 200:
            sound_name = response.headers.get('X-Sound-Name', f'{category}_sound.mp3')
            total_sounds = response.headers.get('X-Total-Sounds', 'unknown')
            print(f"✅ Retrieved sound: {sound_name}")
            print(f"   Total sounds in {category}: {total_sounds}")
            return response.content, sound_name
        else:
            print(f"❌ Error: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   {error_data.get('error', response.text)}")
            except:
                print(f"   {response.text}")
            return None, None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None

def save_results(result):
    """Save the generated image and optionally sound"""
    # Create output directory
    output_dir = Path.cwd() / "panorama_output"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_files = []
    
    # Save image
    if result.get('image'):
        image_file = output_dir / f"panorama_{timestamp}.png"
        with open(image_file, 'wb') as f:
            f.write(result['image'])
        
        print(f"🖼️  Image saved: {image_file}")
        print(f"   Size: {len(result['image']) / 1024 / 1024:.2f} MB")
        saved_files.append(('image', image_file))
    
    # Save sound if present
    if result.get('sound'):
        sound_name = result.get('sound_name', 'ambient.mp3')
        sound_file = output_dir / f"sound_{timestamp}_{sound_name}"
        with open(sound_file, 'wb') as f:
            f.write(result['sound'])
        
        print(f"🎵 Sound saved: {sound_file}")
        print(f"   Size: {len(result['sound']) / 1024 / 1024:.2f} MB")
        saved_files.append(('sound', sound_file))
    
    # Save metadata
    transcription = result.get('transcription', '')
    prompt = result.get('prompt', '')
    category = result.get('category', '')
    
    if transcription or prompt or category:
        metadata_file = output_dir / f"panorama_{timestamp}.txt"
        with open(metadata_file, 'w') as f:
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"\n")
            if category:
                f.write(f"Category: {category}\n")
                f.write(f"\n")
            if transcription:
                f.write(f"Original Transcription:\n")
                f.write(f"{transcription}\n")
                f.write(f"\n")
            if prompt:
                f.write(f"Enhanced Prompt:\n")
                f.write(f"{prompt}\n")
            if result.get('sound_name'):
                f.write(f"\n")
                f.write(f"Sound File: {result.get('sound_name')}\n")
        
        print(f"📄 Metadata saved: {metadata_file}")
    
    return saved_files, output_dir

def select_category():
    """Prompt user to select a category"""
    print("📂 Available Categories:")
    print("")
    for i, cat in enumerate(VALID_CATEGORIES, 1):
        print(f"   {i}. {cat.capitalize()}")
    print("")
    
    while True:
        choice = input("Select category (1-4 or name): ").strip().lower()
        
        # Check if number
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(VALID_CATEGORIES):
                return VALID_CATEGORIES[idx]
        # Check if name
        elif choice in VALID_CATEGORIES:
            return choice
        
        print("❌ Invalid choice. Please enter 1-4 or a category name.")

def main_image_only():
    """Main function for image-only mode (original)"""
    print("")
    print("=" * 70)
    print("🎨 Azure 360° Panorama Generator - Image Only Mode")
    print("=" * 70)
    print("")
    print("This script will:")
    print("  1. Record your voice describing a landscape")
    print("  2. Send it to Azure for processing")
    print("  3. Generate a 360° panorama image")
    print("")
    
    # Test API connectivity
    test_connectivity()
    
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
    result = send_to_api_image_only(audio_bytes)
    
    if result and result.get('image'):
        # Save results
        saved_files, output_dir = save_results(result)
        
        print("")
        print("=" * 70)
        print("✅ SUCCESS! Your 360° panorama is ready!")
        print("=" * 70)
        print("")
        print(f"📂 Output folder: {output_dir.absolute()}")
        for file_type, file_path in saved_files:
            print(f"   {file_type}: {file_path.name}")
        print("")
    else:
        print("")
        print("=" * 70)
        print("❌ Failed to generate panorama")
        print("=" * 70)
        print("")
        sys.exit(1)

def main_with_sound():
    """Main function for image + sound mode"""
    print("")
    print("=" * 70)
    print("🎨🎵 Azure 360° Panorama Generator - With Sound Mode")
    print("=" * 70)
    print("")
    print("This script will:")
    print("  1. Record your voice describing a landscape")
    print("  2. Send it to Azure for processing")
    print("  3. Generate a 360° panorama image")
    print("  4. Categorize the scene (beach/forest/mountain/garden)")
    print("  5. Fetch a matching ambient sound")
    print("")
    
    # Test API connectivity
    test_connectivity()
    
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
    result = send_to_api_with_sound(audio_bytes)
    
    if result and result.get('image'):
        # Save results
        saved_files, output_dir = save_results(result)
        
        print("")
        print("=" * 70)
        print("✅ SUCCESS! Your 360° panorama and sound are ready!")
        print("=" * 70)
        print("")
        print(f"📂 Output folder: {output_dir.absolute()}")
        for file_type, file_path in saved_files:
            print(f"   {file_type}: {file_path.name}")
        print("")
    else:
        print("")
        print("=" * 70)
        print("❌ Failed to generate panorama")
        print("=" * 70)
        print("")
        sys.exit(1)

def main_sound_only():
    """Main function for sound-only mode"""
    print("")
    print("=" * 70)
    print("🎵 Azure Random Sound Retrieval")
    print("=" * 70)
    print("")
    
    # Test API connectivity
    test_connectivity()
    
    print("")
    
    # Select category
    category = select_category()
    print(f"\n✅ Selected: {category.capitalize()}")
    print("")
    
    # Get sound
    sound_bytes, sound_name = get_random_sound(category)
    
    if sound_bytes:
        # Save sound
        output_dir = Path.cwd() / "panorama_output"
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sound_file = output_dir / f"sound_{category}_{timestamp}.mp3"
        
        with open(sound_file, 'wb') as f:
            f.write(sound_bytes)
        
        print("")
        print("=" * 70)
        print("✅ SUCCESS! Sound downloaded!")
        print("=" * 70)
        print("")
        print(f"🎵 Sound: {sound_file}")
        print(f"   Size: {len(sound_bytes) / 1024 / 1024:.2f} MB")
        print("")
        print(f"To play: open {sound_file}")
        print("")
    else:
        print("")
        print("=" * 70)
        print("❌ Failed to retrieve sound")
        print("=" * 70)
        print("")
        sys.exit(1)

def test_connectivity():
    """Test API connectivity"""
    print("🔍 Testing Azure API connectivity...")
    try:
        test_response = requests.get(
            "https://endpoint-gtfbdtb7bwf2hsfb.westeurope-01.azurewebsites.net",
            timeout=10
        )
        print("✅ Azure API is accessible")
    except Exception as e:
        print(f"⚠️  Warning: Cannot reach Azure API ({e})")
        print("")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)

def main():
    """Main entry point with argument parsing"""
    parser = argparse.ArgumentParser(
        description='Azure 360° Panorama Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 test-from-anywhere.py                # Image only (original mode)
  python3 test-from-anywhere.py --with-sound   # Image + matching sound
  python3 test-from-anywhere.py --sound-only   # Get random sound for a category
        """
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--with-sound', action='store_true',
                       help='Generate image AND get matching ambient sound')
    group.add_argument('--sound-only', action='store_true',
                       help='Get a random sound for a category (no image)')
    
    args = parser.parse_args()
    
    if args.sound_only:
        main_sound_only()
    elif args.with_sound:
        main_with_sound()
    else:
        main_image_only()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("")
        print("")
        print("⚠️  Interrupted by user")
        sys.exit(1)
