/**
 * @file ga700_modbus.c
 * @brief Implementation of ESP32 ESP-IDF RS-485 Modbus RTU Driver for Yaskawa GA700 VFD
 */

#include <string.h>
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "ga700_modbus.h"

static const char *TAG = "GA700_MODBUS";

static ga700_config_t g_dev_cfg;
static bool g_initialized = false;
static uint16_t g_last_command_val = 0; // State cache for command register 0x0001

// ============================================================================
// Modbus RTU Helper Functions
// ============================================================================

/**
 * @brief Calculate Modbus RTU CRC16 (Polynomial 0xA001)
 */
static uint16_t modbus_crc16(const uint8_t *buffer, uint16_t length)
{
    uint16_t crc = 0xFFFF;
    for (uint16_t pos = 0; pos < length; pos++) {
        crc ^= (uint16_t)buffer[pos];
        for (int i = 8; i != 0; i--) {
            if ((crc & 0x0001) != 0) {
                crc >>= 1;
                crc ^= 0xA001;
            } else {
                crc >>= 1;
            }
        }
    }
    return crc;
}

// ============================================================================
// Core RS-485 Communication Functions
// ============================================================================

esp_err_t ga700_init(const ga700_config_t *config)
{
    if (config != NULL) {
        g_dev_cfg = *config;
    } else {
        // Set Defaults
        g_dev_cfg.uart_port  = GA700_DEFAULT_UART_PORT;
        g_dev_cfg.tx_pin     = GA700_DEFAULT_TX_PIN;
        g_dev_cfg.rx_pin     = GA700_DEFAULT_RX_PIN;
        g_dev_cfg.rts_pin    = GA700_DEFAULT_RTS_PIN;
        g_dev_cfg.baud_rate  = GA700_DEFAULT_BAUD_RATE;
        g_dev_cfg.parity     = GA700_DEFAULT_PARITY; // GA700 default H5-03 = 0 (No parity)
        g_dev_cfg.slave_addr = GA700_DEFAULT_SLAVE_ADDR;
        g_dev_cfg.timeout_ms = GA700_DEFAULT_TIMEOUT_MS;
    }

    uart_config_t uart_config = {
        .baud_rate           = g_dev_cfg.baud_rate,
        .data_bits           = UART_DATA_8_BITS,
        .parity              = g_dev_cfg.parity,
        .stop_bits           = UART_STOP_BITS_1,
        .flow_ctrl           = UART_HW_FLOWCTRL_DISABLE,
        .rx_flow_ctrl_thresh = 122,
        .source_clk          = UART_SCLK_DEFAULT,
    };

    ESP_LOGI(TAG, "Initializing RS-485 UART%d [TX:%d, RX:%d, RTS/DE:%d] Baud:%ld Parity:%d SlaveID:%d",
             g_dev_cfg.uart_port, g_dev_cfg.tx_pin, g_dev_cfg.rx_pin, g_dev_cfg.rts_pin,
             g_dev_cfg.baud_rate, g_dev_cfg.parity, g_dev_cfg.slave_addr);

    // Driver install
    esp_err_t err = uart_driver_install(g_dev_cfg.uart_port, 256, 256, 0, NULL, 0);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to install UART driver: %s", esp_err_to_name(err));
        return err;
    }

    err = uart_param_config(g_dev_cfg.uart_port, &uart_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to configure UART params: %s", esp_err_to_name(err));
        return err;
    }

    // Set UART pins (TX, RX, RTS for RS-485 DE/RE control, CTS unused)
    err = uart_set_pin(g_dev_cfg.uart_port, g_dev_cfg.tx_pin, g_dev_cfg.rx_pin, g_dev_cfg.rts_pin, UART_PIN_NO_CHANGE);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set UART pins: %s", esp_err_to_name(err));
        return err;
    }

    // Enable Hardware RS-485 Half-Duplex Mode
    // ESP32 hardware automatically pulls RTS high during TX and low during RX
    err = uart_set_mode(g_dev_cfg.uart_port, UART_MODE_RS485_HALF_DUPLEX);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set UART RS-485 mode: %s", esp_err_to_name(err));
        return err;
    }

    // Set RX timeout (in symbol periods)
    err = uart_set_rx_timeout(g_dev_cfg.uart_port, 3);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set UART RX timeout: %s", esp_err_to_name(err));
        return err;
    }

    g_initialized = true;
    ESP_LOGI(TAG, "RS-485 driver successfully initialized for Yaskawa GA700");
    return ESP_OK;
}

// Read Holding Registers (Function Code 0x03)
esp_err_t ga700_read_holding_registers(uint16_t start_reg, uint16_t num_regs, uint16_t *out_buf)
{
    if (!g_initialized) {
        ESP_LOGE(TAG, "Driver not initialized!");
        return ESP_ERR_INVALID_STATE;
    }
    if (num_regs == 0 || num_regs > 125 || out_buf == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    // Flush RX buffer
    uart_flush_input(g_dev_cfg.uart_port);

    // Build Request Frame
    uint8_t req[8];
    req[0] = g_dev_cfg.slave_addr;
    req[1] = 0x03; // Function Code: Read Holding Registers
    req[2] = (start_reg >> 8) & 0xFF;
    req[3] = start_reg & 0xFF;
    req[4] = (num_regs >> 8) & 0xFF;
    req[5] = num_regs & 0xFF;

    uint16_t crc = modbus_crc16(req, 6);
    req[6] = crc & 0xFF;        // CRC Low byte
    req[7] = (crc >> 8) & 0xFF; // CRC High byte

    ESP_LOGD(TAG, "TX Read Regs Req [start=0x%04X, count=%d]:", start_reg, num_regs);
    ESP_LOG_BUFFER_HEX_LEVEL(TAG, req, sizeof(req), ESP_LOG_INFO);

    // Send Request
    int tx_bytes = uart_write_bytes(g_dev_cfg.uart_port, (const char *)req, sizeof(req));
    if (tx_bytes != sizeof(req)) {
        ESP_LOGE(TAG, "Failed to send read request");
        return ESP_FAIL;
    }

    // Wait for transmit complete
    uart_wait_tx_done(g_dev_cfg.uart_port, pdMS_TO_TICKS(100));

    // Expected Response Length: SlaveAddr(1) + FC(1) + ByteCount(1) + Data(2*N) + CRC(2)
    int expected_len = 5 + (num_regs * 2);
    uint8_t resp[256];
    int rx_bytes = uart_read_bytes(g_dev_cfg.uart_port, resp, expected_len, pdMS_TO_TICKS(g_dev_cfg.timeout_ms));

    if (rx_bytes < 5) {
        ESP_LOGW(TAG, "Read timeout or incomplete response (received %d bytes, expected %d)", rx_bytes, expected_len);
        return ESP_ERR_TIMEOUT;
    }

    ESP_LOGD(TAG, "RX Response (%d bytes):", rx_bytes);
    ESP_LOG_BUFFER_HEX_LEVEL(TAG, resp, rx_bytes, ESP_LOG_INFO);

    // Verify CRC
    uint16_t calc_crc = modbus_crc16(resp, rx_bytes - 2);
    uint16_t rx_crc = resp[rx_bytes - 2] | (resp[rx_bytes - 1] << 8);
    if (calc_crc != rx_crc) {
        ESP_LOGE(TAG, "CRC Error: Calc=0x%04X, Recv=0x%04X", calc_crc, rx_crc);
        return ESP_ERR_INVALID_CRC;
    }

    // Check Slave Address
    if (resp[0] != g_dev_cfg.slave_addr) {
        ESP_LOGE(TAG, "Slave Address Mismatch: Expected %d, Got %d", g_dev_cfg.slave_addr, resp[0]);
        return ESP_ERR_INVALID_RESPONSE;
    }

    // Check Exception Code
    if (resp[1] & 0x80) {
        ESP_LOGE(TAG, "Modbus Exception Received FC=0x%02X, Code=0x%02X", resp[1], resp[2]);
        return ESP_ERR_INVALID_RESPONSE;
    }

    if (resp[1] != 0x03) {
        ESP_LOGE(TAG, "Unexpected Function Code: 0x%02X", resp[1]);
        return ESP_ERR_INVALID_RESPONSE;
    }

    // Extract Data
    uint8_t byte_count = resp[2];
    if (byte_count != num_regs * 2) {
        ESP_LOGE(TAG, "Byte count mismatch: Expected %d, Got %d", num_regs * 2, byte_count);
        return ESP_ERR_INVALID_RESPONSE;
    }

    for (int i = 0; i < num_regs; i++) {
        out_buf[i] = (resp[3 + (i * 2)] << 8) | resp[4 + (i * 2)];
    }

    return ESP_OK;
}

esp_err_t ga700_read_holding_register(uint16_t reg_addr, uint16_t *out_val)
{
    return ga700_read_holding_registers(reg_addr, 1, out_val);
}

// Write Single Register (Function Code 0x06)
esp_err_t ga700_write_single_register(uint16_t reg_addr, uint16_t value)
{
    if (!g_initialized) {
        ESP_LOGE(TAG, "Driver not initialized!");
        return ESP_ERR_INVALID_STATE;
    }

    uart_flush_input(g_dev_cfg.uart_port);

    // Build Request Frame
    uint8_t req[8];
    req[0] = g_dev_cfg.slave_addr;
    req[1] = 0x06; // Function Code: Write Single Register
    req[2] = (reg_addr >> 8) & 0xFF;
    req[3] = reg_addr & 0xFF;
    req[4] = (value >> 8) & 0xFF;
    req[5] = value & 0xFF;

    uint16_t crc = modbus_crc16(req, 6);
    req[6] = crc & 0xFF;
    req[7] = (crc >> 8) & 0xFF;

    // Send Request
    int tx_bytes = uart_write_bytes(g_dev_cfg.uart_port, (const char *)req, sizeof(req));
    if (tx_bytes != sizeof(req)) {
        ESP_LOGE(TAG, "Failed to send write request");
        return ESP_FAIL;
    }

    uart_wait_tx_done(g_dev_cfg.uart_port, pdMS_TO_TICKS(100));

    // Response for FC06 is 8 bytes echo
    uint8_t resp[8];
    int rx_bytes = uart_read_bytes(g_dev_cfg.uart_port, resp, sizeof(resp), pdMS_TO_TICKS(g_dev_cfg.timeout_ms));

    if (rx_bytes < 8) {
        ESP_LOGW(TAG, "Write timeout or incomplete response (received %d bytes)", rx_bytes);
        return ESP_ERR_TIMEOUT;
    }

    // Verify CRC
    uint16_t calc_crc = modbus_crc16(resp, 6);
    uint16_t rx_crc = resp[6] | (resp[7] << 8);
    if (calc_crc != rx_crc) {
        ESP_LOGE(TAG, "CRC Error on Write Response: Calc=0x%04X, Recv=0x%04X", calc_crc, rx_crc);
        return ESP_ERR_INVALID_CRC;
    }

    // Check Exception Code
    if (resp[1] & 0x80) {
        ESP_LOGE(TAG, "Modbus Write Exception Code: 0x%02X", resp[2]);
        return ESP_ERR_INVALID_RESPONSE;
    }

    return ESP_OK;
}

// ============================================================================
// High-Level Drive Control Functions
// ============================================================================

esp_err_t ga700_run_forward(void)
{
    ESP_LOGI(TAG, "Sending Command: RUN FORWARD");
    g_last_command_val = GA700_CMD_RUN; // Bit 0 = 1, Bit 1 = 0
    return ga700_write_single_register(GA700_REG_COMMAND, g_last_command_val);
}

esp_err_t ga700_run_reverse(void)
{
    ESP_LOGI(TAG, "Sending Command: RUN REVERSE");
    g_last_command_val = GA700_CMD_RUN | GA700_CMD_REVERSE; // Bit 0 = 1, Bit 1 = 1
    return ga700_write_single_register(GA700_REG_COMMAND, g_last_command_val);
}

esp_err_t ga700_stop(void)
{
    ESP_LOGI(TAG, "Sending Command: STOP");
    g_last_command_val &= ~GA700_CMD_RUN; // Clear Bit 0
    return ga700_write_single_register(GA700_REG_COMMAND, g_last_command_val);
}

esp_err_t ga700_set_frequency(float freq_hz)
{
    if (freq_hz < 0.0f || freq_hz > 400.0f) {
        ESP_LOGE(TAG, "Invalid frequency: %.2f Hz (Allowed: 0 to 400 Hz)", freq_hz);
        return ESP_ERR_INVALID_ARG;
    }

    // GA700 Frequency resolution is 0.01 Hz (e.g. 50.00 Hz = 5000)
    uint16_t raw_val = (uint16_t)(freq_hz * 100.0f + 0.5f);
    ESP_LOGI(TAG, "Setting Frequency Reference: %.2f Hz (Raw: %u)", freq_hz, raw_val);
    return ga700_write_single_register(GA700_REG_FREQ_REF, raw_val);
}

esp_err_t ga700_reset_fault(void)
{
    ESP_LOGI(TAG, "Sending Command: FAULT RESET");
    uint16_t cmd_reset = g_last_command_val | GA700_CMD_FAULT_RESET;
    esp_err_t err = ga700_write_single_register(GA700_REG_COMMAND, cmd_reset);
    vTaskDelay(pdMS_TO_TICKS(100));
    // Clear the reset bit
    ga700_write_single_register(GA700_REG_COMMAND, g_last_command_val);
    return err;
}

esp_err_t ga700_read_telemetry(ga700_telemetry_t *telem)
{
    if (telem == NULL) return ESP_ERR_INVALID_ARG;

    // Read 12 registers starting from 0x0020 (0x0020 to 0x002B)
    uint16_t regs[12];
    esp_err_t err = ga700_read_holding_registers(GA700_REG_STATUS_1, 12, regs);
    if (err != ESP_OK) {
        return err;
    }

    telem->raw_status       = regs[0];  // 0x0020 Status 1
    telem->fault_code       = regs[1];  // 0x0021 Fault Code
    telem->alarm_code       = regs[2];  // 0x0022 Alarm Code
    telem->output_freq_hz   = regs[4] / 100.0f;  // 0x0024 Output Frequency (0.01 Hz)
    telem->output_voltage_v = regs[5] / 10.0f;   // 0x0025 Output Voltage (0.1 V)
    telem->output_current_a = regs[6] / 10.0f;   // 0x0026 Output Current (0.1 A)
    telem->dc_bus_voltage_v = (float)regs[8];    // 0x0028 DC Bus Voltage (1 V)
    telem->output_torque_pct= regs[11] / 10.0f;  // 0x002B Output Torque (0.1 %)

    // Decode status bits
    telem->is_running      = (telem->raw_status & GA700_STATUS_RUNNING) != 0;
    telem->is_reverse      = (telem->raw_status & GA700_STATUS_REVERSE) != 0;
    telem->is_speed_agreed = (telem->raw_status & GA700_STATUS_SPEED_AGREE) != 0;
    telem->is_ready        = (telem->raw_status & GA700_STATUS_READY) != 0;
    telem->is_alarm        = (telem->raw_status & GA700_STATUS_ALARM) != 0;
    telem->is_fault        = (telem->raw_status & GA700_STATUS_FAULT) != 0;

    return ESP_OK;
}

esp_err_t ga700_read_output_current_u1_03(uint16_t *raw_val, float *current_amps)
{
    if (raw_val == NULL && current_amps == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    uint16_t reg_val = 0;
    esp_err_t err = ga700_read_holding_register(GA700_REG_U1_03_CURRENT, &reg_val);
    if (err != ESP_OK) {
        return err;
    }

    if (raw_val != NULL) {
        *raw_val = reg_val;
    }
    if (current_amps != NULL) {
        // Yaskawa GA700 U1-03 standard resolution is 0.01 A (or 0.1 A for large models)
        *current_amps = reg_val / 100.0f;
    }

    return ESP_OK;
}
