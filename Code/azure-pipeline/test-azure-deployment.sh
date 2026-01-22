#!/bin/bash

# Test Azure Function App Deployment

echo "🧪 Testing Azure Function App: endpoint"
echo "=================================================="
echo ""

FUNCTION_URL="https://endpoint-gtfbdtb7bwf2hsfb.westeurope-01.azurewebsites.net"

# Test 1: Check if the function app is accessible
echo "1️⃣ Testing function app availability..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$FUNCTION_URL")

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "204" ]; then
    echo "✅ Function app is accessible (HTTP $HTTP_CODE)"
else
    echo "⚠️  Function app returned HTTP $HTTP_CODE"
fi

echo ""

# Test 2: Check audio-to-image endpoint
echo "2️⃣ Testing /api/audio-to-image endpoint..."
AUDIO_ENDPOINT="$FUNCTION_URL/api/audio-to-image"

# Create a minimal WAV file for testing (1 second of silence)
echo "   Creating test audio file..."
python3 - << 'EOF'
import wave
import struct

with wave.open('/tmp/test_audio.wav', 'wb') as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(16000)
    wav.writeframes(b'\x00\x00' * 16000)
print("   ✅ Test audio file created")
EOF

echo "   Sending request to Azure Function..."
echo "   URL: $AUDIO_ENDPOINT"
echo ""

RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
  -X POST "$AUDIO_ENDPOINT" \
  -H "Content-Type: audio/wav" \
  --data-binary @/tmp/test_audio.wav \
  --max-time 30)

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ SUCCESS! Endpoint is working (HTTP 200)"
    echo ""
    echo "Your public endpoint:"
    echo "  $AUDIO_ENDPOINT"
elif [ "$HTTP_CODE" = "400" ]; then
    echo "✅ Endpoint is accessible (HTTP 400 - expected for silence)"
    echo ""
    echo "Your public endpoint:"
    echo "  $AUDIO_ENDPOINT"
elif [ "$HTTP_CODE" = "404" ]; then
    echo "❌ Endpoint not found (HTTP 404)"
    echo "   Function may not be deployed correctly"
elif [ -z "$HTTP_CODE" ]; then
    echo "⚠️  Request timed out or no response"
else
    echo "⚠️  Unexpected response (HTTP $HTTP_CODE)"
    echo "$RESPONSE" | grep -v "HTTP_CODE:" | head -10
fi

echo ""
echo "=================================================="
echo "📋 Your Azure Function Endpoints:"
echo "=================================================="
echo ""
echo "🎤 Audio to Image (Complete Pipeline - Returns PNG):"
echo "   POST $FUNCTION_URL/api/audio-to-image"
echo ""
echo "🎤🎵 Audio to Image With Sound (NEW - Returns JSON with image+sound):"
echo "   POST $FUNCTION_URL/api/audio-to-image-with-sound"
echo ""
echo "📝 Audio to Prompt (Text Only):"
echo "   POST $FUNCTION_URL/api/audio-to-prompt"
echo ""
echo "🖼️  Generate Image (From Prompt):"
echo "   POST $FUNCTION_URL/api/generate-image"
echo ""
echo "🖼️  Get Random Image:"
echo "   GET $FUNCTION_URL/api/images/{category}"
echo "   Categories: beach, mountain, forest, garden"
echo ""
echo "🎵 Get Random Sound (NEW):"
echo "   GET $FUNCTION_URL/api/sounds/{category}"
echo "   Categories: beach, mountain, forest, garden"
echo ""
echo "=================================================="
echo "Example Usage:"
echo "=================================================="
echo ""
echo "# Get random sound:"
echo "curl \"$FUNCTION_URL/api/sounds/beach\" --output beach_sound.mp3"
echo ""
echo "# Audio to Image (original - returns PNG):"
echo "curl -X POST \"$AUDIO_ENDPOINT\" \\"
echo "  -H \"Content-Type: audio/wav\" \\"
echo "  --data-binary @your_audio.wav \\"
echo "  --output panorama.png"
echo ""
echo "# Audio to Image with Sound (returns JSON):"
echo "curl -X POST \"$FUNCTION_URL/api/audio-to-image-with-sound\" \\"
echo "  -H \"Content-Type: audio/wav\" \\"
echo "  --data-binary @your_audio.wav"
echo ""

# Test GetRandomSound endpoint
echo ""
echo "3️⃣ Testing /api/sounds/beach endpoint..."
SOUND_ENDPOINT="$FUNCTION_URL/api/sounds/beach"
echo "   URL: $SOUND_ENDPOINT"

SOUND_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$SOUND_ENDPOINT" --max-time 30)
SOUND_HTTP_CODE=$(echo "$SOUND_RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)

if [ "$SOUND_HTTP_CODE" = "200" ]; then
    echo "✅ GetRandomSound endpoint is working (HTTP 200)"
elif [ "$SOUND_HTTP_CODE" = "404" ]; then
    echo "⚠️  No sounds found or endpoint not deployed yet (HTTP 404)"
else
    echo "⚠️  Sound endpoint returned HTTP $SOUND_HTTP_CODE"
fi

echo ""

# Cleanup
rm -f /tmp/test_audio.wav
