#!/usr/bin/env python3

"""
Retrieve Random Image or Sound from Azure Blob Storage

This script retrieves a random 360° panorama image or ambient sound from 
a specified category using the Azure Function endpoint.

Usage:
    python3 retrieve-random-image.py                    # Interactive mode (image)
    python3 retrieve-random-image.py beach              # Get random beach image
    python3 retrieve-random-image.py mountain --sound   # Get random mountain sound
    python3 retrieve-random-image.py --sound            # Interactive mode (sound)

Requirements:
    pip3 install requests python-dotenv
"""

import sys
import os
import argparse
import requests
from pathlib import Path
from datetime import datetime

# Try to load dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuration - HARDCODED FOR PORTABILITY (works on any PC without env vars)
API_BASE = "https://endpoint-gtfbdtb7bwf2hsfb.westeurope-01.azurewebsites.net/api"
FUNCTION_KEY = "3LKq6SmNriNUNQ6tXeSsE3JqGRKOj58YypNp5RDWhZ7-AzFu3Cr5Fg=="
VALID_CATEGORIES = ["beach", "mountain", "forest", "garden"]
OUTPUT_DIR = Path(__file__).parent / "retrieved_images"

def get_api_url(endpoint):
    """Build full API URL with function code"""
    url = f"{API_BASE}/{endpoint}"
    if FUNCTION_KEY:
        url = f"{url}?code={FUNCTION_KEY}"
    return url

def retrieve_random_image(category):
    """Retrieve a random image from the specified category"""
    
    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    print("")
    print("🎲 Retrieving Random Image")
    print("=" * 60)
    print(f"   Category: {category.capitalize()}")
    print("")
    
    # Build URL
    url = get_api_url(f"images/{category}")
    
    try:
        print(f"📡 Requesting: {url[:70]}...")
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            # Get metadata from headers
            image_name = response.headers.get('X-Image-Name', f'{category}_image.png')
            total_images = response.headers.get('X-Total-Images', 'unknown')
            
            print(f"✅ Success! Retrieved image from category: {category}")
            print(f"   Image name: {image_name}")
            print(f"   Total images in {category}: {total_images}")
            print("")
            
            # Save the image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = OUTPUT_DIR / f"random_{category}_{timestamp}.png"
            
            with open(output_file, 'wb') as f:
                f.write(response.content)
            
            size_mb = len(response.content) / 1024 / 1024
            print(f"💾 Saved to: {output_file}")
            print(f"   Size: {size_mb:.2f} MB")
            print("")
            print("=" * 60)
            print(f"✅ Image saved successfully!")
            print("=" * 60)
            print("")
            print(f"To open: open {output_file}")
            print("")
            
            return True
            
        elif response.status_code == 404:
            error_data = response.json()
            print(f"❌ {error_data.get('error', 'Not Found')}")
            print(f"   {error_data.get('message', 'No images found')}")
            print("")
            print("💡 Tip: Upload some images first using:")
            print("   python3 record-categorize-and-generate.py")
            return False
            
        elif response.status_code == 400:
            error_data = response.json()
            print(f"❌ {error_data.get('error', 'Bad Request')}")
            print(f"   {error_data.get('message', '')}")
            if 'validCategories' in error_data:
                print(f"   Valid categories: {', '.join(error_data['validCategories'])}")
            return False
            
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            try:
                error_data = response.json()
                print(f"   {error_data}")
            except:
                print(f"   {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Azure Function")
        print("   Check your internet connection")
        return False
        
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def select_category_interactive():
    """Prompt user to select a category"""
    print("")
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
                    return VALID_CATEGORIES[index]
            
            # Check if it's a category name
            if choice in VALID_CATEGORIES:
                return choice
            
            print(f"❌ Invalid selection. Please choose 1-4 or enter: {', '.join(VALID_CATEGORIES)}")
            print("")
        except KeyboardInterrupt:
            print("\n\n⚠️  Cancelled by user")
            sys.exit(1)

def retrieve_random_sound(category):
    """Retrieve a random sound from the specified category"""
    
    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    print("")
    print("🎵 Retrieving Random Sound")
    print("=" * 60)
    print(f"   Category: {category.capitalize()}")
    print("")
    
    # Build URL
    url = get_api_url(f"sounds/{category}")
    
    try:
        print(f"📡 Requesting: {url[:70]}...")
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            # Get metadata from headers
            sound_name = response.headers.get('X-Sound-Name', f'{category}_sound.mp3')
            total_sounds = response.headers.get('X-Total-Sounds', 'unknown')
            
            print(f"✅ Success! Retrieved sound from category: {category}")
            print(f"   Sound name: {sound_name}")
            print(f"   Total sounds in {category}: {total_sounds}")
            print("")
            
            # Save the sound
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = OUTPUT_DIR / f"random_{category}_{timestamp}.mp3"
            
            with open(output_file, 'wb') as f:
                f.write(response.content)
            
            size_mb = len(response.content) / 1024 / 1024
            print(f"💾 Saved to: {output_file}")
            print(f"   Size: {size_mb:.2f} MB")
            print("")
            print("=" * 60)
            print(f"✅ Sound saved successfully!")
            print("=" * 60)
            print("")
            print(f"To play: open {output_file}")
            print("")
            
            return True
            
        elif response.status_code == 404:
            error_data = response.json()
            print(f"❌ {error_data.get('error', 'Not Found')}")
            print(f"   {error_data.get('message', 'No sounds found')}")
            return False
            
        elif response.status_code == 400:
            error_data = response.json()
            print(f"❌ {error_data.get('error', 'Bad Request')}")
            print(f"   {error_data.get('message', '')}")
            if 'validCategories' in error_data:
                print(f"   Valid categories: {', '.join(error_data['validCategories'])}")
            return False
            
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            try:
                error_data = response.json()
                print(f"   {error_data}")
            except:
                print(f"   {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Azure Function")
        print("   Check your internet connection")
        return False
        
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Retrieve random image or sound from Azure',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 retrieve-random-image.py              # Interactive mode (image)
  python3 retrieve-random-image.py beach        # Get random beach image
  python3 retrieve-random-image.py forest       # Get random forest image
  python3 retrieve-random-image.py --sound      # Interactive mode (sound)
  python3 retrieve-random-image.py beach --sound  # Get random beach sound
        """
    )
    
    parser.add_argument('category', nargs='?', default=None,
                        choices=VALID_CATEGORIES,
                        help='Category to retrieve (beach, mountain, forest, garden)')
    parser.add_argument('--sound', '-s', action='store_true',
                        help='Retrieve a sound instead of an image')
    
    args = parser.parse_args()
    
    # Get category
    if args.category:
        category = args.category
    else:
        # Interactive mode
        if args.sound:
            print("")
            print("🎵 Random Ambient Sound Retriever")
            print("=" * 60)
        else:
            print("")
            print("🎨 Random 360° Panorama Image Retriever")
            print("=" * 60)
        category = select_category_interactive()
    
    # Retrieve based on mode
    if args.sound:
        success = retrieve_random_sound(category)
    else:
        success = retrieve_random_image(category)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("")
        print("")
        print("⚠️  Interrupted by user")
        sys.exit(1)
