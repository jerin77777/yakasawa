idf_component_register(
    SRCS "main.c" "ga700_modbus.c"
    INCLUDE_DIRS "."
    REQUIRES driver esp_driver_uart esp_driver_gpio freertos esp_system log
)
