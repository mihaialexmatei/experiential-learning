idf_component_register(SRCS "main.c"
                    INCLUDE_DIRS "."
                    REQUIRES driver esp_wifi nvs_flash esp_netif esp_event mqtt esp_driver_gpio mbedtls json)
