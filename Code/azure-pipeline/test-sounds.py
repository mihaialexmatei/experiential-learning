#!/usr/bin/env python3

"""
Test script for Azure Functions sound endpoints.

Tests:
1. GetRandomSound endpoint - retrieves random ambient sounds by category
2. AudioToImageWithSound endpoint - generates image with matching sound

Usage:
    python3 test-sounds.py [local|azure]
    
    local  - Test against local Azure Functions (default)
    azure  - Test against deployed Azure Functions

Requirements:
    pip3 install requests python-dotenv
"""

import os
import sys
import json
import base64
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")

# Configuration
LOCAL_BASE_URL = "http://localhost:7071/api"
AZURE_BASE_URL = os.getenv("AZURE_FUNCTION_URL", "https://endpoint-gtfbdtb7bwf2hsfb.westeurope-01.azurewebsites.net/api")
FUNCTION_KEY = os.getenv("AZURE_FUNCTION_KEY", "")

VALID_CATEGORIES = ["beach", "mountain", "forest", "garden"]
OUTPUT_DIR = Path(__file__).parent / "test_output"


def get_base_url(environment: str) -> str:
    """Get the base URL based on environment"""
    if environment == "local":
        return LOCAL_BASE_URL
    return AZURE_BASE_URL


def get_headers(environment: str) -> dict:
    """Get headers with function key for Azure"""
    headers = {}
    if environment == "azure" and FUNCTION_KEY:
        headers["x-functions-key"] = FUNCTION_KEY
    return headers


def test_get_random_sound(environment: str, category: str) -> bool:
    """Test the GetRandomSound endpoint"""
    base_url = get_base_url(environment)
    url = f"{base_url}/sounds/{category}"
    
    print(f"\n{'='*60}")
    print(f"🎵 Testing GetRandomSound - Category: {category}")
    print(f"{'='*60}")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, headers=get_headers(environment), timeout=30)
        
        print(f"Status: {response.status_code}")
        print(f"Headers:")
        for key, value in response.headers.items():
            if key.startswith("X-"):
                print(f"  {key}: {value}")
        
        if response.status_code == 200:
            # Save the sound file
            OUTPUT_DIR.mkdir(exist_ok=True)
            sound_name = response.headers.get("X-Sound-Name", f"{category}_unknown.mp3")
            output_path = OUTPUT_DIR / f"test_{sound_name}"
            
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            print(f"✅ Success! Sound saved to: {output_path}")
            print(f"   Size: {len(response.content):,} bytes")
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_all_categories(environment: str) -> dict:
    """Test GetRandomSound for all categories"""
    results = {}
    
    print(f"\n{'#'*60}")
    print(f"# Testing GetRandomSound for all categories")
    print(f"# Environment: {environment}")
    print(f"{'#'*60}")
    
    for category in VALID_CATEGORIES:
        results[category] = test_get_random_sound(environment, category)
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 GetRandomSound Test Summary")
    print(f"{'='*60}")
    for category, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {category}: {status}")
    
    return results


def test_audio_to_image_with_sound(environment: str, audio_file_path: str = None) -> bool:
    """Test the AudioToImageWithSound endpoint"""
    base_url = get_base_url(environment)
    url = f"{base_url}/audio-to-image-with-sound"
    
    print(f"\n{'='*60}")
    print(f"🎨🎵 Testing AudioToImageWithSound")
    print(f"{'='*60}")
    print(f"URL: {url}")
    
    # Use provided audio file or create a test one
    if audio_file_path and Path(audio_file_path).exists():
        with open(audio_file_path, "rb") as f:
            audio_data = f.read()
        print(f"Using audio file: {audio_file_path}")
    else:
        # Check for test audio file in common locations
        test_audio_paths = [
            Path(__file__).parent / "test_audio.wav",
            Path(__file__).parent / "temp" / "test_audio.wav",
        ]
        
        audio_data = None
        for test_path in test_audio_paths:
            if test_path.exists():
                with open(test_path, "rb") as f:
                    audio_data = f.read()
                print(f"Using audio file: {test_path}")
                break
        
        if audio_data is None:
            print("⚠️  No test audio file found. Skipping AudioToImageWithSound test.")
            print("   Create a test_audio.wav file to test this endpoint.")
            return False
    
    try:
        headers = get_headers(environment)
        headers["Content-Type"] = "audio/wav"
        
        print("Sending request... (this may take a few minutes)")
        response = requests.post(url, data=audio_data, headers=headers, timeout=600)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n✅ Success!")
            print(f"   Original transcription: {data.get('originalTranscription', 'N/A')}")
            print(f"   Enhanced prompt: {data.get('enhancedPrompt', 'N/A')[:100]}...")
            print(f"   Category: {data.get('category', 'N/A')}")
            print(f"   Sound name: {data.get('soundName', 'N/A')}")
            print(f"   Message: {data.get('message', 'N/A')}")
            
            # Save image and sound
            OUTPUT_DIR.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if data.get("image"):
                image_bytes = base64.b64decode(data["image"])
                image_path = OUTPUT_DIR / f"combined_test_{timestamp}.png"
                with open(image_path, "wb") as f:
                    f.write(image_bytes)
                print(f"   Image saved: {image_path} ({len(image_bytes):,} bytes)")
            
            if data.get("sound"):
                sound_bytes = base64.b64decode(data["sound"])
                sound_name = data.get("soundName", "sound.mp3")
                sound_path = OUTPUT_DIR / f"combined_test_{timestamp}_{sound_name}"
                with open(sound_path, "wb") as f:
                    f.write(sound_bytes)
                print(f"   Sound saved: {sound_path} ({len(sound_bytes):,} bytes)")
            
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_invalid_category(environment: str) -> bool:
    """Test error handling for invalid category"""
    base_url = get_base_url(environment)
    url = f"{base_url}/sounds/invalid_category"
    
    print(f"\n{'='*60}")
    print(f"🧪 Testing Invalid Category Handling")
    print(f"{'='*60}")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, headers=get_headers(environment), timeout=30)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 400:
            data = response.json()
            print(f"✅ Correctly returned 400 Bad Request")
            print(f"   Error: {data.get('error', 'N/A')}")
            print(f"   Valid categories: {data.get('validCategories', 'N/A')}")
            return True
        else:
            print(f"❌ Expected 400, got {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Main test runner"""
    # Determine environment
    environment = "local"
    if len(sys.argv) > 1:
        if sys.argv[1].lower() in ["azure", "cloud", "deployed"]:
            environment = "azure"
        elif sys.argv[1].lower() in ["local", "dev"]:
            environment = "local"
    
    print("")
    print("=" * 60)
    print("🧪 Azure Functions Sound Endpoints Test Suite")
    print("=" * 60)
    print(f"Environment: {environment.upper()}")
    print(f"Base URL: {get_base_url(environment)}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print("")
    
    # Run tests
    all_passed = True
    
    # Test 1: GetRandomSound for all categories
    category_results = test_all_categories(environment)
    if not all(category_results.values()):
        all_passed = False
    
    # Test 2: Invalid category handling
    if not test_invalid_category(environment):
        all_passed = False
    
    # Test 3: AudioToImageWithSound (only if audio file exists)
    audio_file = None
    if len(sys.argv) > 2:
        audio_file = sys.argv[2]
    
    print(f"\n{'#'*60}")
    print("# Testing AudioToImageWithSound (combined endpoint)")
    print(f"{'#'*60}")
    test_audio_to_image_with_sound(environment, audio_file)
    
    # Final summary
    print(f"\n{'='*60}")
    print("🏁 Final Test Summary")
    print(f"{'='*60}")
    if all_passed:
        print("✅ All GetRandomSound tests passed!")
    else:
        print("⚠️  Some tests failed. Check the output above.")
    
    print(f"\nTest output files saved to: {OUTPUT_DIR}")
    print("")


if __name__ == "__main__":
    main()
