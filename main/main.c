/**
 * @file main.c
 * @brief Test application reading ONLY Yaskawa GA700 U1-03 (0x0042) Output Current
 */

#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_system.h"
#include "ga700_modbus.h"

static const char *TAG = "U1_03_TEST";

void app_main(void)
{
    ESP_LOGI(TAG, "==================================================");
    ESP_LOGI(TAG, " Yaskawa GA700 Parameter U1-03 (0x0042) Test");
    ESP_LOGI(TAG, "==================================================");

    // Configuration for Waveshare Industrial ESP32-S3 Control Board
    ga700_config_t config = {
        .uart_port  = UART_NUM_2,
        .tx_pin     = GPIO_NUM_17,   // Onboard RS485 TX
        .rx_pin     = GPIO_NUM_18,   // Onboard RS485 RX
        .rts_pin    = GPIO_NUM_21,   // Onboard RS485 EN / RTS
        .baud_rate  = 9600,          // Matches GA700 Parameter H5-02 (9600 bps)
        .parity     = UART_PARITY_DISABLE, // Matches GA700 Parameter H5-03 = 0 (No Parity, 8-N-1)
        .slave_addr = 0x1F,             // 31 decimal (Matches GA700 Parameter H5-01 = 1F hex)
        .timeout_ms = 1000
    };

    // Initialize RS-485 Modbus Driver
    esp_err_t ret = ga700_init(&config);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize RS-485 driver!");
        return;
    }

    ESP_LOGI(TAG, "Driver initialized. Starting continuous polling of register 0x0042 (U1-03)...");

    uint16_t raw_current = 0;
    float current_amps = 0.0f;
    uint32_t poll_count = 0;

    while (1) {
        poll_count++;
        ESP_LOGI(TAG, "--------------------------------------------------");
        ESP_LOGI(TAG, "Poll #%lu: Reading Register 0x0042 (U1-03 Output Current)...", poll_count);

        esp_err_t err = ga700_read_output_current_u1_03(&raw_current, &current_amps);

        if (err == ESP_OK) {
            ESP_LOGI(TAG, "SUCCESS! Raw Register: %u (Hex: 0x%04X) | Output Current: %.2f A",
                     raw_current, raw_current, current_amps);
        } else {
            ESP_LOGE(TAG, "READ FAILED: %s", esp_err_to_name(err));
        }

        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
