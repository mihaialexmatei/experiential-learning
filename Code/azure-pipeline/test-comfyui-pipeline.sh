#!/bin/bash

# Test script for Azure Functions + ComfyUI pipeline

echo "🧪 Testing Azure Functions + ComfyUI Pipeline"
echo "=============================================="
echo ""

# Check if Azure Functions is running
echo "1️⃣ Checking Azure Functions..."
FUNC_HEALTH=$(curl -s http://localhost:7071/api/audio-to-prompt -X POST -H "Content-Type: audio/wav" --data-binary @/dev/null 2>&1 | grep -o "No audio file" || echo "NOT_RUNNING")

if [[ $FUNC_HEALTH == *"NOT_RUNNING"* ]]; then
    echo "❌ Azure Functions not responding on port 7071"
    echo "   Run: cd Code/azure-pipeline/dotnet-functions && func start"
    exit 1
else
    echo "✅ Azure Functions is running"
fi

echo ""

# Check ComfyUI URL configuration
echo "2️⃣ Checking ComfyUI configuration..."
COMFY_URL=$(grep -A 1 '"ComfyUIUrl"' Code/azure-pipeline/dotnet-functions/local.settings.json | tail -1 | cut -d'"' -f4)

if [[ $COMFY_URL == *"ngrok"* ]]; then
    echo "✅ ComfyUI URL configured: $COMFY_URL"
else
    echo "⚠️  ComfyUI URL: $COMFY_URL"
    echo "   Make sure to update with your ngrok URL"
fi

echo ""

# Test ComfyUI endpoint
echo "3️⃣ Testing ComfyUI endpoint..."
COMFY_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "$COMFY_URL/health" 2>/dev/null || echo "000")

if [[ $COMFY_HEALTH == "200" ]]; then
    echo "✅ ComfyUI is responding"
elif [[ $COMFY_HEALTH == "000" ]]; then
    echo "❌ Cannot connect to ComfyUI at $COMFY_URL"
    echo "   Make sure ngrok tunnel is running"
else
    echo "⚠️  ComfyUI responded with HTTP $COMFY_HEALTH"
fi

echo ""

# Check Azure credentials
echo "4️⃣ Checking Azure credentials..."
SPEECH_KEY=$(grep -A 1 '"SpeechServiceKey"' Code/azure-pipeline/dotnet-functions/local.settings.json | tail -1 | cut -d'"' -f4)
OPENAI_KEY=$(grep -A 1 '"OpenAIKey"' Code/azure-pipeline/dotnet-functions/local.settings.json | tail -1 | cut -d'"' -f4)

if [[ ! -z "$SPEECH_KEY" ]] && [[ $SPEECH_KEY != "your-key" ]]; then
    echo "✅ Azure Speech Service key configured"
else
    echo "⚠️  Azure Speech Service key not configured"
fi

if [[ ! -z "$OPENAI_KEY" ]] && [[ $OPENAI_KEY != "your-key" ]]; then
    echo "✅ Azure OpenAI key configured"
else
    echo "⚠️  Azure OpenAI key not configured"
fi

echo ""
echo "=============================================="
echo "📋 Summary"
echo "=============================================="
echo "Azure Functions:  ✓"
echo "ComfyUI URL:      $COMFY_URL"
echo "ComfyUI Status:   $([ $COMFY_HEALTH == '200' ] && echo '✓' || echo '⚠')"
echo ""
echo "🚀 To test the complete pipeline:"
echo "   curl -X POST http://localhost:7071/api/audio-to-image \\"
echo "        -H 'Content-Type: audio/wav' \\"
echo "        --data-binary @your_audio.wav \\"
echo "        --output generated_image.png"
echo ""
