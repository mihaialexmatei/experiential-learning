#!/bin/bash

# =====================================================
# Deploy Azure Functions to Function App
# =====================================================
# 
# This script deploys the dotnet-functions project to Azure
# and configures all required application settings.
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - Azure Functions Core Tools installed
#   - .NET 8 SDK installed
#
# Usage:
#   ./deploy-to-azure.sh [function-app-name]
#
# Example:
#   ./deploy-to-azure.sh experiential-learning-functions
#
# =====================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/dotnet-functions"
DEFAULT_FUNCTION_APP="endpoint"
RESOURCE_GROUP="RESEARCH_PROJECT_Mihai_Matei"
FUNCTION_APP="${1:-$DEFAULT_FUNCTION_APP}"

echo ""
echo "======================================================"
echo -e "${BLUE}🚀 Azure Functions Deployment Script${NC}"
echo "======================================================"
echo ""
echo "Function App: $FUNCTION_APP"
echo "Project Dir:  $PROJECT_DIR"
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo -e "${RED}❌ Azure CLI is not installed${NC}"
    echo "   Install it from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check if logged in to Azure
echo -e "${BLUE}📋 Checking Azure login status...${NC}"
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}⚠️  Not logged in to Azure. Running 'az login'...${NC}"
    az login
fi

ACCOUNT_NAME=$(az account show --query name -o tsv)
echo -e "${GREEN}✅ Logged in as: $ACCOUNT_NAME${NC}"
echo ""

# Check if function app exists
echo -e "${BLUE}📋 Checking if function app exists...${NC}"
if ! az functionapp show --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --query name -o tsv &> /dev/null; then
    echo -e "${RED}❌ Function app '$FUNCTION_APP' not found${NC}"
    echo ""
    echo "Available function apps:"
    az functionapp list --query "[].name" -o tsv
    echo ""
    exit 1
fi
echo -e "${GREEN}✅ Function app found: $FUNCTION_APP${NC}"
echo ""

# Load local settings for app configuration
echo -e "${BLUE}📋 Loading local settings...${NC}"
LOCAL_SETTINGS="$PROJECT_DIR/local.settings.json"

if [ ! -f "$LOCAL_SETTINGS" ]; then
    echo -e "${RED}❌ local.settings.json not found at $LOCAL_SETTINGS${NC}"
    exit 1
fi

# Read values from local.settings.json
STORAGE_CONN=$(python3 -c "import json; print(json.load(open('$LOCAL_SETTINGS'))['Values'].get('StorageConnectionString', ''))")
SPEECH_KEY=$(python3 -c "import json; print(json.load(open('$LOCAL_SETTINGS'))['Values'].get('SpeechServiceKey', ''))")
SPEECH_REGION=$(python3 -c "import json; print(json.load(open('$LOCAL_SETTINGS'))['Values'].get('SpeechServiceRegion', ''))")
OPENAI_ENDPOINT=$(python3 -c "import json; print(json.load(open('$LOCAL_SETTINGS'))['Values'].get('OpenAIEndpoint', ''))")
OPENAI_KEY=$(python3 -c "import json; print(json.load(open('$LOCAL_SETTINGS'))['Values'].get('OpenAIKey', ''))")
OPENAI_DEPLOYMENT=$(python3 -c "import json; print(json.load(open('$LOCAL_SETTINGS'))['Values'].get('OpenAIDeploymentName', 'gpt-4o-mini'))")
COMFYUI_URL=$(python3 -c "import json; print(json.load(open('$LOCAL_SETTINGS'))['Values'].get('ComfyUIUrl', ''))")

echo -e "${GREEN}✅ Settings loaded${NC}"
echo ""

# Configure application settings
echo "======================================================"
echo -e "${BLUE}⚙️  Configuring Application Settings${NC}"
echo "======================================================"
echo ""
echo "This will configure the following settings:"
echo "  - StorageConnectionString"
echo "  - SpeechServiceKey (IMPORTANT: Updated key)"
echo "  - SpeechServiceRegion"
echo "  - OpenAIEndpoint"
echo "  - OpenAIKey (IMPORTANT: Updated key)"
echo "  - OpenAIDeploymentName"
echo "  - ComfyUIUrl"
echo ""

# Set application settings
echo -e "${BLUE}Setting StorageConnectionString...${NC}"
az functionapp config appsettings set --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" \
    --settings "StorageConnectionString=$STORAGE_CONN" \
    --output none

echo -e "${BLUE}Setting SpeechServiceKey...${NC}"
az functionapp config appsettings set --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" \
    --settings "SpeechServiceKey=$SPEECH_KEY" \
    --output none

echo -e "${BLUE}Setting SpeechServiceRegion...${NC}"
az functionapp config appsettings set --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" \
    --settings "SpeechServiceRegion=$SPEECH_REGION" \
    --output none

echo -e "${BLUE}Setting OpenAIEndpoint...${NC}"
az functionapp config appsettings set --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" \
    --settings "OpenAIEndpoint=$OPENAI_ENDPOINT" \
    --output none

echo -e "${BLUE}Setting OpenAIKey...${NC}"
az functionapp config appsettings set --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" \
    --settings "OpenAIKey=$OPENAI_KEY" \
    --output none

echo -e "${BLUE}Setting OpenAIDeploymentName...${NC}"
az functionapp config appsettings set --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" \
    --settings "OpenAIDeploymentName=$OPENAI_DEPLOYMENT" \
    --output none

echo -e "${BLUE}Setting ComfyUIUrl...${NC}"
az functionapp config appsettings set --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" \
    --settings "ComfyUIUrl=$COMFYUI_URL" \
    --output none

echo ""
echo -e "${GREEN}✅ Application settings configured${NC}"
echo ""

# Build the project
echo "======================================================"
echo -e "${BLUE}🔨 Building Project${NC}"
echo "======================================================"
echo ""

cd "$PROJECT_DIR"

echo -e "${BLUE}Restoring packages...${NC}"
dotnet restore

echo -e "${BLUE}Building in Release mode...${NC}"
dotnet build --configuration Release

echo -e "${BLUE}Publishing...${NC}"
dotnet publish --configuration Release --output ./publish

echo ""
echo -e "${GREEN}✅ Build completed${NC}"
echo ""

# Deploy to Azure
echo "======================================================"
echo -e "${BLUE}🚀 Deploying to Azure${NC}"
echo "======================================================"
echo ""

echo -e "${BLUE}Deploying functions...${NC}"
func azure functionapp publish "$FUNCTION_APP" --dotnet-isolated

echo ""
echo -e "${GREEN}✅ Deployment completed${NC}"
echo ""

# Get function URL
FUNCTION_URL="https://$FUNCTION_APP.azurewebsites.net/api"

# Print summary
echo "======================================================"
echo -e "${GREEN}✅ Deployment Summary${NC}"
echo "======================================================"
echo ""
echo -e "${GREEN}Function App:${NC} $FUNCTION_APP"
echo -e "${GREEN}Base URL:${NC} $FUNCTION_URL"
echo ""
echo "======================================================"
echo -e "${BLUE}📋 Available Endpoints${NC}"
echo "======================================================"
echo ""
echo -e "${YELLOW}🎤 Audio to Image (Original - Returns PNG):${NC}"
echo "   POST $FUNCTION_URL/audio-to-image"
echo ""
echo -e "${YELLOW}🎤🎵 Audio to Image With Sound (NEW - Returns JSON with image+sound):${NC}"
echo "   POST $FUNCTION_URL/audio-to-image-with-sound"
echo ""
echo -e "${YELLOW}📝 Audio to Prompt:${NC}"
echo "   POST $FUNCTION_URL/audio-to-prompt"
echo ""
echo -e "${YELLOW}🖼️  Generate Image:${NC}"
echo "   POST $FUNCTION_URL/generate-image"
echo ""
echo -e "${YELLOW}🖼️  Get Random Image:${NC}"
echo "   GET $FUNCTION_URL/images/{category}"
echo "   Categories: beach, mountain, forest, garden"
echo ""
echo -e "${YELLOW}🎵 Get Random Sound (NEW):${NC}"
echo "   GET $FUNCTION_URL/sounds/{category}"
echo "   Categories: beach, mountain, forest, garden"
echo ""
echo "======================================================"
echo -e "${BLUE}📝 Unity Integration Example${NC}"
echo "======================================================"
echo ""
echo "For AudioToImageWithSound endpoint (returns JSON):"
echo ""
echo "Response format:"
echo '  {'
echo '    "success": true,'
echo '    "category": "beach",'
echo '    "image": "base64 encoded PNG",'
echo '    "sound": "base64 encoded MP3",'
echo '    "soundName": "beach_waves.mp3"'
echo '  }'
echo ""
echo "======================================================"
echo ""
echo -e "${GREEN}✅ All done! Your functions are now live.${NC}"
echo ""
