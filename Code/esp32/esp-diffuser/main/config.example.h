/**
 * ESP32 Diffuser Configuration
 * 
 * IMPORTANT: Copy this file to config.h and fill in your actual values.
 * DO NOT commit config.h to git - it contains sensitive credentials!
 * 
 * To use:
 * 1. Copy this file: cp config.example.h config.h
 * 2. Edit config.h with your actual values
 * 3. Build and flash the ESP32
 */

#ifndef CONFIG_H
#define CONFIG_H

#include "driver/gpio.h"

// ===========================================
// WiFi Configuration - Primary Network
// ===========================================
#define WIFI_SSID      "YOUR_WIFI_SSID"
#define WIFI_PASSWORD  "YOUR_WIFI_PASSWORD"

// ===========================================
// WiFi Configuration - Fallback Network
// ===========================================
#define WIFI_SSID_2      "YOUR_FALLBACK_WIFI_SSID"
#define WIFI_PASSWORD_2  "YOUR_FALLBACK_WIFI_PASSWORD"

// ===========================================
// Azure IoT Hub Configuration
// ===========================================
#define IOT_HUB_HOSTNAME "YOUR_IOT_HUB.azure-devices.net"
#define DEVICE_ID        "YOUR_DEVICE_ID"  // e.g., "esp0-beach", "esp1-forest", "esp2-garden", "esp3-mountain"
#define DEVICE_KEY       "YOUR_DEVICE_PRIMARY_KEY"

// ===========================================
// Hardware Pin Configuration
// ===========================================
#define RELAY_PIN   GPIO_NUM_16
#define FAN_PIN     GPIO_NUM_27
#define FAN_PIN_2   GPIO_NUM_26
#define RELAY_PIN_2 GPIO_NUM_2

#endif // CONFIG_H
