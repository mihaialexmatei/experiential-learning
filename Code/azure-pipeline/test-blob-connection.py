#!/usr/bin/env python3
"""
Quick test script to verify Azure Blob Storage connection and create container
"""

import os
import sys
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

# Load environment variables
load_dotenv()
o
STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "premade-scenes")

def test_connection():
    print("🧪 Testing Azure Blob Storage Connection...")
    print("")
    
    if not STORAGE_CONNECTION_STRING:
        print("❌ AZURE_STORAGE_CONNECTION_STRING not found in .env")
        return False
    
    try:
        # Create blob service client
        blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
        
        # Test connection by listing containers
        print("✅ Connected to Azure Storage Account")
        print("")
        
        # List existing containers
        print("📦 Existing containers:")
        containers = list(blob_service_client.list_containers())
        if containers:
            for container in containers:
                print(f"   - {container.name}")
        else:
            print("   (none)")
        print("")
        
        # Create or verify premade-scenes container
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        
        try:
            container_client.get_container_properties()
            print(f"✅ Container '{CONTAINER_NAME}' already exists")
        except:
            print(f"📦 Creating container: {CONTAINER_NAME}")
            container_client.create_container()
            print(f"✅ Container '{CONTAINER_NAME}' created successfully")
        
        print("")
        
        # List blobs in the container
        print(f"📸 Images in '{CONTAINER_NAME}':")
        blobs = list(container_client.list_blobs())
        if blobs:
            categories = {"beach": 0, "mountain": 0, "forest": 0, "garden": 0}
            for blob in blobs:
                print(f"   - {blob.name}")
                # Count by category
                for cat in categories.keys():
                    if blob.name.startswith(f"{cat}_"):
                        categories[cat] += 1
            
            print("")
            print("📊 Images by category:")
            for cat, count in categories.items():
                print(f"   {cat.capitalize()}: {count} images")
        else:
            print("   (no images yet)")
        
        print("")
        print("=" * 60)
        print("✅ Connection test PASSED!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"❌ Connection test FAILED: {e}")
        print("")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
