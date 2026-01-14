#!/bin/bash

# Start Azure Functions API
# Run this in one terminal and keep it running

echo "🚀 Starting Azure Functions API..."
echo "=============================================="
echo ""
echo "This will start the audio-to-image pipeline API"
echo "The API will be available at: http://localhost:7071"
echo ""
echo "Endpoints:"
echo "  POST /api/audio-to-image   - Complete pipeline (audio → image)"
echo "  POST /api/audio-to-prompt  - Audio → text prompt only"
echo "  POST /api/generate-image   - Text prompt → image"
echo ""
echo "Press Ctrl+C to stop the API"
echo "=============================================="
echo ""

cd "$(dirname "$0")/dotnet-functions"

# Check if func command exists
if ! command -v func &> /dev/null; then
    echo "❌ Azure Functions Core Tools not found!"
    echo ""
    echo "Install with:"
    echo "  brew install azure-functions-core-tools@4"
    echo ""
    exit 1
fi

# Start the functions
func start
