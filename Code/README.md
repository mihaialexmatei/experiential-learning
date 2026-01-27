# 🌍 360° Immersive Experience Platform

A multisensory immersive experience system that generates 360° panoramic environments with synchronized ambient sounds and scent diffusion, controlled via voice commands.

## ✨ Features

- **Voice-to-Panorama Generation** - Describe a scene and get an AI-generated 360° panoramic image
- **Ambient Sound Integration** - Automatically matched environmental audio (beach waves, forest birds, etc.)
- **Scent Diffusion Control** - ESP32-powered diffusers release matching aromas for full immersion
- **Pre-made Scene Library** - Curated scenes: Beach, Forest, Garden, Mountain
- **Real-time Generation** - On-demand panorama creation via Azure AI services

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Voice Input   │────▶│  Azure Functions │────▶│ 360° Panorama   │
│   (Recording)   │     │  (Speech + GPT)  │     │   + Sound URL   │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │  Azure IoT Hub   │
                        └────────┬─────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│  ESP32 Beach  │       │ ESP32 Forest  │       │ ESP32 Garden  │ ...
│   Diffuser    │       │   Diffuser    │       │   Diffuser    │
└───────────────┘       └───────────────┘       └───────────────┘
```

## 📁 Project Structure

```
Code/
├── azure-pipeline/           # Azure Functions & backend services
│   ├── dotnet-functions/     # .NET Azure Functions
│   │   ├── Functions/        # API endpoints
│   │   │   ├── AudioToImageWithSound.cs  # Main pipeline
│   │   │   ├── GetRandomImage.cs         # Pre-made scenes
│   │   │   └── GetRandomSound.cs         # Ambient sounds
│   │   └── Services/         # ComfyUI integration
│   └── *.py                  # Test scripts
│
└── esp32/
    └── esp-diffuser/         # ESP32 firmware
        ├── main/             # Device firmware (C)
        └── espendpoint/      # Azure Function for IoT control
```

## 🚀 Getting Started

### Prerequisites

- [Azure Account](https://azure.microsoft.com/) with:
  - Azure Functions
  - Azure IoT Hub
  - Azure Blob Storage
  - Azure Speech Services
  - Azure OpenAI
- [ESP-IDF](https://docs.espressif.com/projects/esp-idf/en/latest/) for ESP32 development
- [.NET 8 SDK](https://dotnet.microsoft.com/)
- Python 3.10+

### Configuration

1. **Azure Functions** - Copy example configs and add your credentials:
   ```bash
   cd azure-pipeline/dotnet-functions
   cp local.settings.example.json local.settings.json
   # Edit local.settings.json with your Azure keys
   ```

2. **ESP32 Devices** - Copy config template:
   ```bash
   cd esp32/esp-diffuser/main
   cp config.example.h config.h
   # Edit config.h with WiFi and Azure IoT credentials
   ```

3. **Environment Variables** (for test scripts):
   ```bash
   cd azure-pipeline
   cp .env.example .env
   # Edit .env with your credentials
   ```

### Running Locally

**Azure Functions:**
```bash
cd azure-pipeline/dotnet-functions
func start
```

**ESP32 Firmware:**
```bash
cd esp32/esp-diffuser
idf.py build
idf.py flash
```

## 🔌 API Endpoints

### Generate Panorama from Voice
```
POST /api/audio-to-image-with-sound
Content-Type: audio/wav
Body: <audio file>

Response: { "imageUrl": "...", "soundUrl": "...", "category": "beach" }
```

### Get Random Pre-made Scene
```
GET /api/images/{category}
# category: beach, forest, garden, mountain

Response: { "imageUrl": "...", "category": "beach" }
```

### Get Random Ambient Sound
```
GET /api/sounds/{category}

Response: { "soundUrl": "...", "category": "forest" }
```

### Control ESP32 Diffuser
```
GET /api/{device}/{duration}
# device: esp0-beach, esp1-forest, esp2-garden, esp3-mountain
# duration: minutes (integer) or "stop"

GET /api/stop-all  # Stop all diffusers
```

## 🎯 Scene Categories

| Category | Scent | Sound | Visual |
|----------|-------|-------|--------|
| 🏖️ Beach | Ocean breeze | Waves, seagulls | Coastal panorama |
| 🌲 Forest | Pine, earth | Birds, rustling leaves | Woodland panorama |
| 🌸 Garden | Floral | Bees, gentle wind | Garden panorama |
| ⛰️ Mountain | Fresh alpine | Wind, distant streams | Mountain panorama |

## 🛠️ Tech Stack

- **Backend**: Azure Functions (.NET 8), Python
- **AI Services**: Azure OpenAI (GPT-4o), Azure Speech Services
- **Image Generation**: ComfyUI with Flux model
- **IoT**: Azure IoT Hub, MQTT
- **Hardware**: ESP32, relay modules, scent diffusers
- **Storage**: Azure Blob Storage

## 📄 License

This project was developed as part of a university team project.

## 👥 Team

Experiential Learning Team - Howest University
