#include <stdio.h>
#include <string.h>
#include <time.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "driver/gpio.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_system.h"
#include "nvs_flash.h"
#include "esp_netif.h"
#include "esp_tls.h"
#include "mqtt_client.h"
#include "esp_sntp.h"
#include "cJSON.h"
#include "mbedtls/md.h"
#include "mbedtls/base64.h"

// WiFi Configuration
#define WIFI_SSID      "Howest-SmartTech-Hub"
#define WIFI_PASSWORD  "zPovZi0RyeLVu8Jim"

// Fallback WiFi Configuration
#define WIFI_SSID_2      "alexpie"
#define WIFI_PASSWORD_2  "Parola1!"

// Azure IoT Hub Configuration
#define IOT_HUB_HOSTNAME "espcontrol.azure-devices.net"
#define DEVICE_ID        "esp2-garden"
#define DEVICE_KEY       "/YZltTRS93nXap3INSd/EauBdsxJ4RCeuWDK75QrvDQ="

// Define the relay control pin
#define RELAY_PIN GPIO_NUM_16
#define FAN_PIN GPIO_NUM_27
#define FAN_PIN_2 GPIO_NUM_26
#define RELAY_PIN_2 GPIO_NUM_2

static const char *TAG = "ESP-DIFFUSER";
static EventGroupHandle_t s_wifi_event_group;
static esp_mqtt_client_handle_t mqtt_client = NULL;
static bool time_synced = false;

#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT      BIT1

static int s_retry_num = 0;
#define MAX_RETRY 10
static int wifi_network = 0; // 0 = first network, 1 = second network

// DigiCert Global Root G2 - Azure IoT Hub Root CA
static const char *azure_root_ca = 
"-----BEGIN CERTIFICATE-----\n"
"MIIDjjCCAnagAwIBAgIQAzrx5qcRqaC7KGSxHQn65TANBgkqhkiG9w0BAQsFADBh\n"
"MQswCQYDVQQGEwJVUzEVMBMGA1UEChMMRGlnaUNlcnQgSW5jMRkwFwYDVQQLExB3\n"
"d3cuZGlnaWNlcnQuY29tMSAwHgYDVQQDExdEaWdpQ2VydCBHbG9iYWwgUm9vdCBH\n"
"MjAeFw0xMzA4MDExMjAwMDBaFw0zODAxMTUxMjAwMDBaMGExCzAJBgNVBAYTAlVT\n"
"MRUwEwYDVQQKEwxEaWdpQ2VydCBJbmMxGTAXBgNVBAsTEHd3dy5kaWdpY2VydC5j\n"
"b20xIDAeBgNVBAMTF0RpZ2lDZXJ0IEdsb2JhbCBSb290IEcyMIIBIjANBgkqhkiG\n"
"9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuzfNNNx7a8myaJCtSnX/RrohCgiN9RlUyfuI\n"
"2/Ou8jqJkTx65qsGGmvPrC3oXgkkRLpimn7Wo6h+4FR1IAWsULecYxpsMNzaHxmx\n"
"1x7e/dfgy5SDN67sH0NO3Xss0r0upS/kqbitOtSZpLYl6ZtrAGCSYP9PIUkY92eQ\n"
"q2EGnI/yuum06ZIya7XzV+hdG82MHauVBJVJ8zUtluNJbd134/tJS7SsVQepj5Wz\n"
"tCO7TG1F8PapspUwtP1MVYwnSlcUfIKdzXOS0xZKBgyMUNGPHgm+F6HmIcr9g+UQ\n"
"vIOlCsRnKPZzFBQ9RnbDhxSJITRNrw9FDKZJobq7nMWxM4MphQIDAQABo0IwQDAP\n"
"BgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwIBhjAdBgNVHQ4EFgQUTiJUIBiV\n"
"5uNu5g/6+rkS7QYXjzkwDQYJKoZIhvcNAQELBQADggEBAGBnKJRvDkhj6zHd6mcY\n"
"1Yl9PMCcit0BKkS2PErKighwECsHLZoAoUbrCsKAUM7yoC7bpwR6yrcDDiLG5jk3\n"
"y7M65UVdtyHThjCs7ruYQtcVVLv+4bFsWMa9Njwz4wMG5LH1xB7QE4XsHf8qKqFf\n"
"uSKYaODM8TjM3sVM9FXWmzsbfC3GErNzzKcv7K+g/GssQeR/ZReL+kHbMUfFcdKg\n"
"GB8djB8EfxjsQkV6SUES9nxM8a5dC5zQB6tA7OmSZpWv5bPWLvXCXPgT7N3N6prD\n"
"jjCP4NIvMYz7p7+9mTGWG8u0+o6IlJ0HLWXQR3PUqpJ3lWP+dMvjZlWVLnlGHpHI\n"
"oAo=\n"
"-----END CERTIFICATE-----\n";

// Generate SAS token for Azure IoT Hub
static char* generate_sas_token(const char* resource_uri, const char* key, int expiry_time) {
    static char sas_token[512];
    char string_to_sign[256];
    unsigned char decoded_key[64];
    size_t decoded_key_len;
    unsigned char hmac_result[32];
    unsigned char base64_signature[64];
    size_t base64_len;
    
    snprintf(string_to_sign, sizeof(string_to_sign), "%s\n%d", resource_uri, expiry_time);
    
    mbedtls_base64_decode(decoded_key, sizeof(decoded_key), &decoded_key_len, 
                          (const unsigned char*)key, strlen(key));
    
    mbedtls_md_context_t ctx;
    mbedtls_md_init(&ctx);
    mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), 1);
    mbedtls_md_hmac_starts(&ctx, decoded_key, decoded_key_len);
    mbedtls_md_hmac_update(&ctx, (const unsigned char*)string_to_sign, strlen(string_to_sign));
    mbedtls_md_hmac_finish(&ctx, hmac_result);
    mbedtls_md_free(&ctx);
    
    mbedtls_base64_encode(base64_signature, sizeof(base64_signature), &base64_len, 
                          hmac_result, sizeof(hmac_result));
    base64_signature[base64_len] = '\0';
    
    char encoded_sig[128];
    int j = 0;
    for (size_t i = 0; i < base64_len && j < (int)sizeof(encoded_sig) - 4; i++) {
        if (base64_signature[i] == '+') {
            encoded_sig[j++] = '%'; encoded_sig[j++] = '2'; encoded_sig[j++] = 'B';
        } else if (base64_signature[i] == '/') {
            encoded_sig[j++] = '%'; encoded_sig[j++] = '2'; encoded_sig[j++] = 'F';
        } else if (base64_signature[i] == '=') {
            encoded_sig[j++] = '%'; encoded_sig[j++] = '3'; encoded_sig[j++] = 'D';
        } else {
            encoded_sig[j++] = base64_signature[i];
        }
    }
    encoded_sig[j] = '\0';
    
    snprintf(sas_token, sizeof(sas_token), 
             "SharedAccessSignature sr=%s&sig=%s&se=%d",
             resource_uri, encoded_sig, expiry_time);
    
    return sas_token;
}

// WiFi event handler
static void wifi_event_handler(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_retry_num < MAX_RETRY) {
            esp_wifi_connect();
            s_retry_num++;
            ESP_LOGI(TAG, "Retry to connect to the AP");
        } else {
            xEventGroupSetBits(s_wifi_event_group, WIFI_FAIL_BIT);
        }
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        ESP_LOGI(TAG, "Got IP:" IPSTR, IP2STR(&event->ip_info.ip));
        s_retry_num = 0;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

// Initialize WiFi with fallback
void wifi_init_sta(void) {
    s_wifi_event_group = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, &instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL, &instance_got_ip));

    // Try first network
    wifi_network = 0;
    wifi_config_t wifi_config = {
        .sta = {
            .ssid = WIFI_SSID,
            .password = WIFI_PASSWORD,
            .threshold.authmode = WIFI_AUTH_OPEN,
            .scan_method = WIFI_ALL_CHANNEL_SCAN,
            .sort_method = WIFI_CONNECT_AP_BY_SIGNAL,
        },
    };
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "Trying first WiFi network: %s", WIFI_SSID);
    EventBits_t bits = xEventGroupWaitBits(s_wifi_event_group, WIFI_CONNECTED_BIT | WIFI_FAIL_BIT, pdFALSE, pdFALSE, portMAX_DELAY);

    if (bits & WIFI_CONNECTED_BIT) {
        ESP_LOGI(TAG, "Connected to WiFi: %s", WIFI_SSID);
    } else {
        ESP_LOGE(TAG, "Failed to connect to first WiFi, trying fallback...");
        
        // Clear event bits and reset retry counter
        xEventGroupClearBits(s_wifi_event_group, WIFI_CONNECTED_BIT | WIFI_FAIL_BIT);
        s_retry_num = 0;
        wifi_network = 1;
        
        // Stop WiFi
        esp_wifi_stop();
        vTaskDelay(pdMS_TO_TICKS(1000));
        
        // Try second network
        wifi_config_t wifi_config_2 = {
            .sta = {
                .ssid = WIFI_SSID_2,
                .password = WIFI_PASSWORD_2,
                .threshold.authmode = WIFI_AUTH_OPEN,
                .scan_method = WIFI_ALL_CHANNEL_SCAN,
                .sort_method = WIFI_CONNECT_AP_BY_SIGNAL,
            },
        };
        ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config_2));
        ESP_ERROR_CHECK(esp_wifi_start());
        
        ESP_LOGI(TAG, "Trying fallback WiFi network: %s", WIFI_SSID_2);
        bits = xEventGroupWaitBits(s_wifi_event_group, WIFI_CONNECTED_BIT | WIFI_FAIL_BIT, pdFALSE, pdFALSE, portMAX_DELAY);
        
        if (bits & WIFI_CONNECTED_BIT) {
            ESP_LOGI(TAG, "Connected to fallback WiFi: %s", WIFI_SSID_2);
        } else {
            ESP_LOGE(TAG, "Failed to connect to both WiFi networks");
        }
    }
}

// Time sync callback
void time_sync_notification_cb(struct timeval *tv) {
    ESP_LOGI(TAG, "Time synchronized");
    time_synced = true;
}

// Initialize SNTP
void init_sntp(void) {
    ESP_LOGI(TAG, "Initializing SNTP");
    esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
    esp_sntp_setservername(0, "pool.ntp.org");
    sntp_set_time_sync_notification_cb(time_sync_notification_cb);
    esp_sntp_init();
    
    int retry = 0;
    while (!time_synced && retry < 30) {
        ESP_LOGI(TAG, "Waiting for time sync... (%d)", retry);
        vTaskDelay(pdMS_TO_TICKS(1000));
        retry++;
    }
}

// Relay task parameters
typedef struct {
    int duration_minutes;
} relay_task_params_t;

void relay_task(void *pvParameters) {
    relay_task_params_t *params = (relay_task_params_t *)pvParameters;
    int duration = params->duration_minutes;
    free(params);
    
    ESP_LOGI(TAG, "Activating fans on GPIO 27 and 26 for %d minutes", duration);
    gpio_set_level(FAN_PIN, 0);
    gpio_set_level(FAN_PIN_2, 0);
    ESP_LOGI(TAG, "Fans ON");
    
    vTaskDelay(pdMS_TO_TICKS(duration * 60 * 1000));
    
    gpio_set_level(FAN_PIN, 1);
    gpio_set_level(FAN_PIN_2, 1);
    ESP_LOGI(TAG, "Fans OFF");
    
    vTaskDelete(NULL);
}

// MQTT event handler
static void mqtt_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data) {
    esp_mqtt_event_handle_t event = event_data;
    
    switch ((esp_mqtt_event_id_t)event_id) {
        case MQTT_EVENT_CONNECTED: {
            ESP_LOGI(TAG, "Connected to Azure IoT Hub!");
            char topic[128];
            snprintf(topic, sizeof(topic), "devices/%s/messages/devicebound/#", DEVICE_ID);
            esp_mqtt_client_subscribe(mqtt_client, topic, 1);
            ESP_LOGI(TAG, "Subscribed to: %s", topic);
            break;
        }
            
        case MQTT_EVENT_DISCONNECTED:
            ESP_LOGI(TAG, "Disconnected from Azure IoT Hub");
            break;
            
        case MQTT_EVENT_DATA: {
            ESP_LOGI(TAG, "Received message!");
            ESP_LOGI(TAG, "Data: %.*s", event->data_len, event->data);
            
            cJSON *json = cJSON_ParseWithLength(event->data, event->data_len);
            if (json != NULL) {
                cJSON *command = cJSON_GetObjectItem(json, "command");
                cJSON *duration = cJSON_GetObjectItem(json, "duration");
                
                if (cJSON_IsString(command) && cJSON_IsNumber(duration)) {
                    const char *cmd = command->valuestring;
                    int dur = duration->valueint;
                    
                    ESP_LOGI(TAG, "Command: %s, Duration: %d", cmd, dur);
                    
                    if (strcmp(cmd, "on") == 0) {
                        relay_task_params_t *params = malloc(sizeof(relay_task_params_t));
                        params->duration_minutes = dur;
                        xTaskCreate(relay_task, "relay_task", 2048, params, 5, NULL);
                    } else if (strcmp(cmd, "off") == 0) {
                        gpio_set_level(FAN_PIN, 1);
                        gpio_set_level(FAN_PIN_2, 1);
                        ESP_LOGI(TAG, "Fans OFF");
                    }
                }
                cJSON_Delete(json);
            }
            break;
        }
            
        case MQTT_EVENT_ERROR:
            ESP_LOGE(TAG, "MQTT error");
            break;
            
        default:
            break;
    }
}

// Initialize Azure IoT Hub connection
void azure_iot_init(void) {
    time_t now;
    time(&now);
    int expiry = now + 86400; // 24 hours
    
    char resource_uri[128];
    snprintf(resource_uri, sizeof(resource_uri), "%s%%2Fdevices%%2F%s", IOT_HUB_HOSTNAME, DEVICE_ID);
    
    char *sas_token = generate_sas_token(resource_uri, DEVICE_KEY, expiry);
    ESP_LOGI(TAG, "SAS token generated");
    
    char mqtt_uri[128];
    snprintf(mqtt_uri, sizeof(mqtt_uri), "mqtts://%s:8883", IOT_HUB_HOSTNAME);
    
    char username[256];
    snprintf(username, sizeof(username), "%s/%s/?api-version=2021-04-12", IOT_HUB_HOSTNAME, DEVICE_ID);
    
    esp_mqtt_client_config_t mqtt_cfg = {
        .broker = {
            .address.uri = mqtt_uri,
            .verification.certificate = azure_root_ca,
        },
        .credentials = {
            .username = username,
            .authentication.password = sas_token,
            .client_id = DEVICE_ID,
        },
    };
    
    mqtt_client = esp_mqtt_client_init(&mqtt_cfg);
    esp_mqtt_client_register_event(mqtt_client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    esp_mqtt_client_start(mqtt_client);
    
    ESP_LOGI(TAG, "MQTT client started");
}

void app_main(void) {
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    gpio_reset_pin(RELAY_PIN);
    gpio_set_direction(RELAY_PIN, GPIO_MODE_OUTPUT);
    gpio_set_level(RELAY_PIN, 0);
    
    gpio_reset_pin(FAN_PIN);
    gpio_set_direction(FAN_PIN, GPIO_MODE_OUTPUT);
    gpio_set_level(FAN_PIN, 1);
    
    gpio_reset_pin(FAN_PIN_2);
    gpio_set_direction(FAN_PIN_2, GPIO_MODE_OUTPUT);
    gpio_set_level(FAN_PIN_2, 1);
    
    gpio_reset_pin(RELAY_PIN_2);
    gpio_set_direction(RELAY_PIN_2, GPIO_MODE_OUTPUT);
    gpio_set_level(RELAY_PIN_2, 1);
    
    ESP_LOGI(TAG, "GPIO 27 and 26 configured for fan control");

    wifi_init_sta();
    init_sntp();
    azure_iot_init();

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(10000));
    }
}