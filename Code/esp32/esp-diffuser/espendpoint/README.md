# ESP Endpoint Azure Function

Simple Azure Function to control ESP32 devices via Azure IoT Hub.

## Setup

1. **Get IoT Hub Service Connection String**:
   - Go to Azure Portal → Your IoT Hub → Shared access policies → service
   - Copy the connection string

2. **Update local.settings.json**:
   - Replace `YOUR_SERVICE_KEY_HERE` with your actual service key

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run locally**:
   ```bash
   func start
   ```

## Usage

Call the endpoint with:
```
http://localhost:7071/api/esp0-beach/2
```

- `esp0-beach` = device name (URL-friendly)
- `2` = duration in minutes

## Deploy to Azure

1. Create Function App in Azure Portal
2. Set `IOT_HUB_CONNECTION_STRING` in Application Settings
3. Deploy:
   ```bash
   func azure functionapp publish espendpoint
   ```

## Production URL

After deployment:
```
https://espendpoint.azurewebsites.net/api/esp0-beach/2
```
