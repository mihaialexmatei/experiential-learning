#!/usr/bin/env python3
"""Simple script to get a random sound for a chosen category"""

import requests

API_URL = "https://endpoint-gtfbdtb7bwf2hsfb.westeurope-01.azurewebsites.net/api/sounds"
CATEGORIES = ["beach", "mountain", "forest", "garden"]

print("🎵 Random Sound Retriever")
print("=" * 40)
print("\nAvailable categories:")
for i, cat in enumerate(CATEGORIES, 1):
    print(f"  {i}. {cat}")

print()
choice = input("Choose a category (1-4 or name): ").strip().lower()

# Parse choice
if choice.isdigit() and 1 <= int(choice) <= 4:
    category = CATEGORIES[int(choice) - 1]
elif choice in CATEGORIES:
    category = choice
else:
    print(f"❌ Invalid choice. Use 1-4 or: {', '.join(CATEGORIES)}")
    exit(1)

print(f"\n🔄 Getting random {category} sound...")

# Fetch sound
try:
    resp = requests.get(f"{API_URL}/{category}", timeout=30)
    
    if resp.status_code == 200:
        sound_name = resp.headers.get('X-Sound-Name', 'unknown.mp3')
        total_sounds = resp.headers.get('X-Total-Sounds', '?')
        
        # Save to file
        output = f"{category}_sound.mp3"
        with open(output, 'wb') as f:
            f.write(resp.content)
        
        print(f"✅ Success!")
        print(f"   Sound: {sound_name}")
        print(f"   Size: {len(resp.content):,} bytes")
        print(f"   Total {category} sounds: {total_sounds}")
        print(f"   Saved to: {output}")
    else:
        print(f"❌ Error {resp.status_code}: {resp.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")
