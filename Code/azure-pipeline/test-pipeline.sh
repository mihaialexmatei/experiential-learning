#!/bin/bash

# Test script for the image generation pipeline
# Make sure both services are running before executing this script

echo "======================================"
echo "Image Generation Pipeline Test Script"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if FastAPI service is running
echo "${YELLOW}1. Checking FastAPI service...${NC}"
if curl -s http://localhost:8000/ > /dev/null; then
    echo "${GREEN}✓ FastAPI service is running${NC}"
else
    echo "${RED}✗ FastAPI service is not running${NC}"
    echo "  Start it with: cd Code/azure-pipeline/local-model && python3 -m uvicorn api_server:app --host 0.0.0.0 --port 8000"
    exit 1
fi

echo ""

# Test FastAPI directly
echo "${YELLOW}2. Testing FastAPI image generation...${NC}"
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "beautiful mountain landscape at sunset",
    "width": 512,
    "height": 512,
    "num_inference_steps": 20
  }' \
  --output test-fastapi.png \
  --silent

if [ -f "test-fastapi.png" ]; then
    FILE_SIZE=$(stat -f%z test-fastapi.png 2>/dev/null || stat -c%s test-fastapi.png 2>/dev/null)
    if [ "$FILE_SIZE" -gt 10000 ]; then
        echo "${GREEN}✓ FastAPI generated image successfully (${FILE_SIZE} bytes)${NC}"
    else
        echo "${RED}✗ Generated image is too small (${FILE_SIZE} bytes) - might be black${NC}"
    fi
else
    echo "${RED}✗ Failed to generate image via FastAPI${NC}"
fi

echo ""

# Check if Azure Functions is running
echo "${YELLOW}3. Checking Azure Functions...${NC}"
if curl -s http://localhost:7071/api/audio-to-prompt > /dev/null 2>&1; then
    echo "${GREEN}✓ Azure Functions is running${NC}"
else
    echo "${RED}✗ Azure Functions is not running${NC}"
    echo "  Start it with: cd Code/azure-pipeline/dotnet-functions && func start"
    exit 1
fi

echo ""

# Test GenerateImage function
echo "${YELLOW}4. Testing GenerateImage function...${NC}"
curl -X POST http://localhost:7071/api/generate-image \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "serene forest with morning mist",
    "width": 512,
    "height": 512,
    "numInferenceSteps": 20
  }' \
  --output test-function.png \
  --silent

if [ -f "test-function.png" ]; then
    FILE_SIZE=$(stat -f%z test-function.png 2>/dev/null || stat -c%s test-function.png 2>/dev/null)
    if [ "$FILE_SIZE" -gt 10000 ]; then
        echo "${GREEN}✓ GenerateImage function generated image successfully (${FILE_SIZE} bytes)${NC}"
    else
        echo "${RED}✗ Generated image is too small (${FILE_SIZE} bytes) - might be black${NC}"
    fi
else
    echo "${RED}✗ Failed to generate image via Function${NC}"
fi

echo ""
echo "======================================"
echo "Test Results:"
echo "======================================"
echo "Generated files:"
ls -lh test-*.png 2>/dev/null || echo "No test images generated"
echo ""
echo "To view images: open test-fastapi.png test-function.png"
echo ""
echo "${YELLOW}Note: Image generation takes 30-50 seconds per image${NC}"
