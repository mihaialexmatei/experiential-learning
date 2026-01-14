#!/bin/bash

# Quick setup script for the audio recording pipeline

echo "🔧 Setting up Audio Recording Pipeline"
echo "=============================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found!"
    exit 1
fi
echo "✅ Python 3 installed"

# Check Azure Functions Core Tools
if ! command -v func &> /dev/null; then
    echo "❌ Azure Functions Core Tools not installed"
    echo ""
    echo "Install with:"
    echo "  brew install azure-functions-core-tools@4"
    echo ""
    exit 1
fi
echo "✅ Azure Functions Core Tools installed"

# Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip3 install --quiet sounddevice numpy requests

if [ $? -eq 0 ]; then
    echo "✅ Python packages installed"
else
    echo "⚠️  Some packages failed to install"
    echo "   Try manually: pip3 install sounddevice numpy requests"
fi

# Create directories
echo ""
echo "📁 Creating directories..."
mkdir -p results
mkdir -p temp
echo "✅ Directories created"

# Make scripts executable
echo ""
echo "🔐 Making scripts executable..."
chmod +x start-api.sh
chmod +x test-comfyui-pipeline.sh
echo "✅ Scripts are executable"

echo ""
echo "=============================================="
echo "✅ Setup Complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo ""
echo "1️⃣  Terminal 1 - Start the API:"
echo "   ./start-api.sh"
echo ""
echo "2️⃣  Terminal 2 - Record and generate:"
echo "   python3 record-and-generate.py 10"
echo ""
echo "📚 For more info, see RECORDING_GUIDE.md"
echo ""
