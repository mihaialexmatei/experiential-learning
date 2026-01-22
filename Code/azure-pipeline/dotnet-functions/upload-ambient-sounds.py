#!/usr/bin/env python3

"""
Upload Ambient Sound Files to Azure Blob Storage

This script uploads audio files from the ambient_sound folder to Azure Blob Storage.
Files are organized in category subfolders (beach, forest, mountain, garden) and
uploaded with the naming convention: {category}_{filename}

Usage:
    python3 upload-ambient-sounds.py

Requirements:
    pip3 install azure-storage-blob python-dotenv
"""

import os
import sys
from pathlib import Path
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

# Configuration
STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = "sounds"
AMBIENT_SOUND_DIR = Path(__file__).parent / "ambient_sound"
VALID_CATEGORIES = ["beach", "forest", "mountain", "garden"]
AUDIO_EXTENSIONS = [".mp3", ".wav", ".ogg", ".m4a"]

def get_unique_blob_name(container_client, base_name):
    """Generate a unique blob name by adding a number suffix if needed"""
    blob_name = base_name
    counter = 2
    
    while container_client.get_blob_client(blob_name).exists():
        # Split filename and extension
        name_parts = base_name.rsplit(".", 1)
        if len(name_parts) == 2:
            blob_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
        else:
            blob_name = f"{base_name}_{counter}"
        counter += 1
    
    return blob_name

def upload_ambient_sounds():
    """Upload all ambient sound files to Azure Blob Storage"""
    
    if not STORAGE_CONNECTION_STRING:
        print("❌ Error: AZURE_STORAGE_CONNECTION_STRING not found in .env file")
        sys.exit(1)
    
    if not AMBIENT_SOUND_DIR.exists():
        print(f"❌ Error: ambient_sound directory not found at {AMBIENT_SOUND_DIR}")
        sys.exit(1)
    
    print("")
    print("=" * 70)
    print("🎵 Uploading Ambient Sound Files to Azure Blob Storage")
    print("=" * 70)
    print(f"📁 Source: {AMBIENT_SOUND_DIR}")
    print(f"📦 Container: {CONTAINER_NAME}")
    print("")
    
    try:
        # Connect to blob storage
        blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        
        # Create container if it doesn't exist
        if not container_client.exists():
            print(f"📦 Creating container '{CONTAINER_NAME}'...")
            container_client.create_container()
            print(f"✅ Container created")
        else:
            print(f"✅ Container '{CONTAINER_NAME}' exists")
        
        print("")
        
        uploaded_count = 0
        skipped_count = 0
        
        # Iterate through category folders
        for category in VALID_CATEGORIES:
            category_dir = AMBIENT_SOUND_DIR / category
            
            if not category_dir.exists():
                print(f"⚠️  Skipping '{category}' - folder not found")
                continue
            
            # Find all audio files in this category
            audio_files = []
            for ext in AUDIO_EXTENSIONS:
                audio_files.extend(category_dir.glob(f"*{ext}"))
            
            if not audio_files:
                print(f"⚠️  No audio files found in '{category}' folder")
                continue
            
            print(f"📂 Processing '{category}' category ({len(audio_files)} files)...")
            
            for audio_file in audio_files:
                # Generate blob name with category prefix
                base_blob_name = f"{category}_{audio_file.name}"
                blob_name = get_unique_blob_name(container_client, base_blob_name)
                
                # Upload file
                blob_client = container_client.get_blob_client(blob_name)
                
                try:
                    with open(audio_file, "rb") as data:
                        blob_client.upload_blob(data, overwrite=False)
                    
                    if blob_name != base_blob_name:
                        print(f"   ✅ Uploaded: {audio_file.name} → {blob_name} (renamed to avoid duplicate)")
                    else:
                        print(f"   ✅ Uploaded: {audio_file.name} → {blob_name}")
                    
                    uploaded_count += 1
                
                except Exception as e:
                    print(f"   ❌ Failed to upload {audio_file.name}: {e}")
                    skipped_count += 1
            
            print("")
        
        # Summary
        print("=" * 70)
        print(f"✅ Upload Complete!")
        print(f"   Uploaded: {uploaded_count} files")
        if skipped_count > 0:
            print(f"   Skipped: {skipped_count} files (errors)")
        print("=" * 70)
        print("")
        print(f"🔗 View files at: https://portal.azure.com")
        print("")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    upload_ambient_sounds()
