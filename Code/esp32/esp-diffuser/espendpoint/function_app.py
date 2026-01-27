import azure.functions as func
import logging
import json
import os
import requests
import hashlib
import hmac
import base64
from urllib.parse import quote_plus
import time

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Enable CORS for easy integration with other services
app.enable_cors = True

# IoT Hub configuration
IOT_HUB_NAME = "espcontrol"
SHARED_ACCESS_KEY = "Ztu3+zjBFGPHiRuXFFBEMO+YXxujYGBJKAIoTP0xHNs="
POLICY_NAME = "service"

# Device mapping
DEVICE_MAPPING = {
    'esp0-beach': 'esp0-breach',
    'esp0-breach': 'esp0-breach',
    'esp1-forest': 'esp1-forest',
    'esp2-garden': 'esp2-garden',
    'esp2-mountain': 'esp3-mountain',  # Redirect esp2-mountain to esp3-mountain
    'esp3-garden': 'esp2-garden',  # Redirect esp3-garden to esp2-garden
    'esp3-mountain': 'esp3-mountain',
    # Add more devices as needed
}

def send_command_to_device(device_id, command, duration=0):
    """Helper function to send a command to a specific device"""
    try:
        # Create message payload
        message_payload = {
            "command": command,
            "duration": duration
        }
        
        # Generate SAS token for the specific device endpoint
        resource_uri = f"{IOT_HUB_NAME}.azure-devices.net/devices/{device_id}"
        expiry = str(int(time.time()) + 3600)
        string_to_sign = f"{quote_plus(resource_uri)}\n{expiry}"
        
        key = base64.b64decode(SHARED_ACCESS_KEY)
        signature = base64.b64encode(
            hmac.new(key, string_to_sign.encode('utf-8'), hashlib.sha256).digest()
        ).decode('utf-8')
        
        sas_token = f"SharedAccessSignature sr={quote_plus(resource_uri)}&sig={quote_plus(signature)}&se={expiry}&skn={POLICY_NAME}"
        
        # Send message to IoT Hub
        url = f"https://{IOT_HUB_NAME}.azure-devices.net/devices/{device_id}/messages/devicebound?api-version=2021-04-12"
        headers = {
            "Authorization": sas_token,
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, headers=headers, json=message_payload, timeout=10)
        
        return response.status_code == 204
    except Exception as e:
        logging.error(f'Error sending command to {device_id}: {str(e)}')
        return False

@app.route(route="{device}/{duration:int}", methods=["GET", "POST"])
def control_device(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing device control request')
    
    try:
        # Get parameters from URL
        device = req.route_params.get('device')
        duration = req.route_params.get('duration')
        
        if not device or not duration:
            return func.HttpResponse(
                "Missing device or duration parameter",
                status_code=400
            )
        
        device_id = DEVICE_MAPPING.get(device)
        if not device_id:
            return func.HttpResponse(
                f"Unknown device: {device}",
                status_code=404
            )
        
        # Send command to device
        success = send_command_to_device(device_id, "on", int(duration))
        
        if success:
            logging.info(f'Successfully sent message to {device_id}')
            return func.HttpResponse(
                json.dumps({
                    "status": "success",
                    "device": device_id,
                    "duration": duration,
                    "message": f"Device {device} activated for {duration} minutes"
                }),
                mimetype="application/json",
                status_code=200
            )
        else:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Failed to send message"
                }),
                mimetype="application/json",
                status_code=500
            )
        
    except Exception as e:
        logging.error(f'Error: {str(e)}')
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            mimetype="application/json",
            status_code=500
        )

@app.route(route="{device}/stop", methods=["GET", "POST"])
def stop_device(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing device stop request')
    
    try:
        device = req.route_params.get('device')
        
        if not device:
            return func.HttpResponse(
                "Missing device parameter",
                status_code=400
            )
        
        device_id = DEVICE_MAPPING.get(device)
        if not device_id:
            return func.HttpResponse(
                f"Unknown device: {device}",
                status_code=404
            )
        
        # Send stop command to device
        success = send_command_to_device(device_id, "off", 0)
        
        if success:
            logging.info(f'Successfully sent stop command to {device_id}')
            return func.HttpResponse(
                json.dumps({
                    "status": "success",
                    "device": device_id,
                    "message": f"Stop command sent to {device}"
                }),
                mimetype="application/json",
                status_code=200
            )
        else:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Failed to send stop command"
                }),
                mimetype="application/json",
                status_code=500
            )
        
    except Exception as e:
        logging.error(f'Error: {str(e)}')
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            mimetype="application/json",
            status_code=500
        )

@app.route(route="stop-all", methods=["GET", "POST"])
def stop_all_devices(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing stop all devices request')
    
    try:
        results = {}
        all_device_ids = set(DEVICE_MAPPING.values())
        
        for device_id in all_device_ids:
            success = send_command_to_device(device_id, "off", 0)
            results[device_id] = "success" if success else "failed"
            logging.info(f'Stop command for {device_id}: {"success" if success else "failed"}')
        
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "message": "Stop command sent to all devices",
                "devices": results
            }),
            mimetype="application/json",
            status_code=200
        )
        
    except Exception as e:
        logging.error(f'Error: {str(e)}')
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            mimetype="application/json",
            status_code=500
        )
