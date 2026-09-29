idf_component_register(
    SRCS "main.c" "ga700_modbus.c" "generated_params.c" "param_handlers.c"
    INCLUDE_DIRS "."
    REQUIRES driver esp_driver_uart esp_driver_gpio freertos esp_system log esp_wifi esp_event nvs_flash esp_netif esp_http_server lwip
)
