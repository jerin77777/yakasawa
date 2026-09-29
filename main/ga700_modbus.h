/**
 * @file ga700_modbus.h
 * @brief ESP32 ESP-IDF RS-485 Modbus RTU Driver for Yaskawa GA700 VFD
 */

#ifndef GA700_MODBUS_H
#define GA700_MODBUS_H

#include <stdint.h>
#include <stdbool.h>
#include "esp_err.h"
#include "driver/uart.h"
#include "driver/gpio.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Default RS-485 Hardware Configuration (Matches Waveshare Industrial ESP32-S3)
// ============================================================================
#define GA700_DEFAULT_UART_PORT      UART_NUM_2
#define GA700_DEFAULT_TX_PIN         GPIO_NUM_17   // Onboard RS485 TX
#define GA700_DEFAULT_RX_PIN         GPIO_NUM_18   // Onboard RS485 RX
#define GA700_DEFAULT_RTS_PIN        GPIO_NUM_21   // Onboard RS485 EN / RTS
#define GA700_DEFAULT_BAUD_RATE      9600          // Matches GA700 parameter H5-02
#define GA700_DEFAULT_PARITY         UART_PARITY_DISABLE // Matches GA700 parameter H5-03 = 0 (No parity)
#define GA700_DEFAULT_SLAVE_ADDR     0x1F          // 31 decimal (Matches GA700 parameter H5-01 = 1F hex)
#define GA700_DEFAULT_TIMEOUT_MS     1000

// ============================================================================
// Yaskawa GA700 MEMOBUS / Modbus RTU Register Addresses (HEX)
// ============================================================================
#define GA700_REG_COMMAND            0x0001   // Drive Operation Command (Write)
#define GA700_REG_FREQ_REF           0x0002   // Frequency Reference (0.01 Hz units) (Write)
#define GA700_REG_STATUS_1           0x0020   // Drive Status 1 (Read)
#define GA700_REG_FAULT_CODE         0x0021   // Fault Contents (Read)
#define GA700_REG_ALARM_CODE         0x0022   // Alarm Contents (Read)
#define GA700_REG_OUTPUT_FREQ        0x0024   // Output Frequency (0.01 Hz units) (Read)
#define GA700_REG_OUTPUT_VOLTAGE     0x0025   // Output Voltage (0.1 V units) (Read)
#define GA700_REG_OUTPUT_CURRENT     0x0026   // Output Current (0.1 A units) (Read)
#define GA700_REG_OUTPUT_POWER       0x0027   // Output Power (0.1 kW units) (Read)
#define GA700_REG_DC_BUS_VOLTAGE     0x0028   // DC Bus Voltage (1 V units) (Read)
#define GA700_REG_OUTPUT_TORQUE      0x002B   // Output Torque (0.1 % units) (Read)
#define GA700_REG_U1_01_FREQ_REF     0x0040   // Monitor U1-01: Frequency Reference (Read)
#define GA700_REG_U1_02_OUTPUT_FREQ  0x0041   // Monitor U1-02: Output Frequency (Read)
#define GA700_REG_U1_03_CURRENT      0x0042   // Monitor U1-03: Output Current (Read)
#define GA700_REG_D1_01_FREQ_REF     0x0280   // Parameter d1-01: Frequency Reference 1 (Write)

// ============================================================================
// Bitmasks for GA700 Command Register (0x0001)
// ============================================================================
#define GA700_CMD_RUN                (1 << 0) // Bit 0: 1 = Run, 0 = Stop
#define GA700_CMD_REVERSE            (1 << 1) // Bit 1: 1 = Reverse, 0 = Forward
#define GA700_CMD_EXTERNAL_FAULT     (1 << 2) // Bit 2: External Fault (EF0)
#define GA700_CMD_FAULT_RESET        (1 << 3) // Bit 3: 1 = Fault Reset

// ============================================================================
// Bitmasks for GA700 Status 1 Register (0x0020)
// ============================================================================
#define GA700_STATUS_RUNNING         (1 << 0) // Bit 0: Drive is running
#define GA700_STATUS_ZERO_SPEED      (1 << 1) // Bit 1: Zero speed
#define GA700_STATUS_REVERSE         (1 << 2) // Bit 2: Running in Reverse
#define GA700_STATUS_RESET_INPUT     (1 << 3) // Bit 3: Reset signal active
#define GA700_STATUS_SPEED_AGREE     (1 << 4) // Bit 4: Frequency agreement (At target speed)
#define GA700_STATUS_READY           (1 << 5) // Bit 5: Drive ready
#define GA700_STATUS_ALARM           (1 << 6) // Bit 6: Alarm / Minor fault
#define GA700_STATUS_FAULT           (1 << 7) // Bit 7: Major fault active
#define GA700_STATUS_OPE_ERROR       (1 << 8) // Bit 8: Parameter setting error (oPE)

// ============================================================================
// Configuration Structure
// ============================================================================
typedef struct {
    uart_port_t uart_port;
    gpio_num_t  tx_pin;
    gpio_num_t  rx_pin;
    gpio_num_t  rts_pin;       // Hardware RTS for RS-485 transceiver DE/RE
    uint32_t    baud_rate;
    uart_parity_t parity;       // UART_PARITY_EVEN (default), UART_PARITY_DISABLE, UART_PARITY_ODD
    uint8_t     slave_addr;     // Node address (default 1)
    uint32_t    timeout_ms;
} ga700_config_t;

// ============================================================================
// GA700 Telemetry & Status Structure
// ============================================================================
typedef struct {
    bool is_running;
    bool is_reverse;
    bool is_speed_agreed;
    bool is_ready;
    bool is_alarm;
    bool is_fault;
    uint16_t raw_status;
    uint16_t fault_code;
    uint16_t alarm_code;
    float output_freq_hz;
    float output_voltage_v;
    float output_current_a;
    float dc_bus_voltage_v;
    float output_torque_pct;
} ga700_telemetry_t;

// ============================================================================
// Public Function Prototypes
// ============================================================================

/**
 * @brief Initialize the ESP32 UART in RS-485 half-duplex mode for GA700.
 * 
 * @param config Pointer to configuration struct (Pass NULL to use defaults)
 * @return esp_err_t ESP_OK on success
 */
esp_err_t ga700_init(const ga700_config_t *config);

/**
 * @brief Read a single 16-bit Modbus Holding Register (Function Code 0x03)
 * 
 * @param reg_addr Register address (e.g., 0x0020)
 * @param out_val Pointer to store received value
 * @return esp_err_t ESP_OK on success
 */
esp_err_t ga700_read_holding_register(uint16_t reg_addr, uint16_t *out_val);

/**
 * @brief Read multiple consecutive 16-bit Modbus Holding Registers (FC 0x03)
 * 
 * @param start_reg Starting register address
 * @param num_regs Number of registers to read
 * @param out_buf Buffer to store register values
 * @return esp_err_t ESP_OK on success
 */
esp_err_t ga700_read_holding_registers(uint16_t start_reg, uint16_t num_regs, uint16_t *out_buf);

/**
 * @brief Write a single 16-bit Modbus Holding Register (Function Code 0x06)
 * 
 * @param reg_addr Register address (e.g., 0x0001 or 0x0002)
 * @param value 16-bit value to write
 * @return esp_err_t ESP_OK on success
 */
esp_err_t ga700_write_single_register(uint16_t reg_addr, uint16_t value);

// ----------------------------------------------------------------------------
// High-Level Drive Control Functions
// ----------------------------------------------------------------------------

/**
 * @brief Send Run command to GA700 (Forward direction)
 * @return esp_err_t ESP_OK on success
 */
esp_err_t ga700_run_forward(void);

/**
 * @brief Send Run command to GA700 (Reverse direction)
 * @return esp_err_t ESP_OK on success
 */
esp_err_t ga700_run_reverse(void);

/**
 * @brief Send Stop command to GA700
 * @return esp_err_t ESP_OK on success
 */
esp_err_t ga700_stop(void);

/**
 * @brief Set output frequency reference in Hertz (e.g., 50.0 Hz)
 * @param freq_hz Frequency in Hz (e.g. 35.5)
 * @return esp_err_t ESP_OK on success
 */
esp_err_t ga700_set_frequency(float freq_hz);

/**
 * @brief Send Fault Reset signal to GA700
 * @return esp_err_t ESP_OK on success
 */
esp_err_t ga700_reset_fault(void);

/**
 * @brief Write Frequency Reference 1 (d1-01 / Register 0x0280)
 * @param freq_hz Frequency in Hz (e.g. 50.00 Hz)
 * @return esp_err_t ESP_OK on success
 */
esp_err_t ga700_write_frequency_d1_01(float freq_hz);

/**
 * @brief Write Frequency to Active Frequency Reference register (0x0002)
 * @param freq_hz Frequency in Hz (e.g. 50.00 Hz)
 * @return esp_err_t ESP_OK on success
 */
esp_err_t ga700_write_frequency_both(float freq_hz);

/**
 * @brief Read Monitor U1-01: Frequency Reference (Register 0x0040)
 * @param raw_val Pointer to store raw 16-bit register value
 * @param freq_hz Pointer to store converted frequency in Hz
 * @return esp_err_t ESP_OK on success
 */
esp_err_t ga700_read_frequency_u1_01(uint16_t *raw_val, float *freq_hz);

/**
 * @brief Read Monitor U1-02: Output Frequency (Register 0x0041)
 * @param raw_val Pointer to store raw 16-bit register value
 * @param freq_hz Pointer to store converted frequency in Hz
 * @return esp_err_t ESP_OK on success
 */
esp_err_t ga700_read_frequency_u1_02(uint16_t *raw_val, float *freq_hz);

/**
 * @brief Read Monitor U1-03: Output Current (Register 0x0042)
 * @param raw_val Pointer to store raw 16-bit register value
 * @param current_amps Pointer to store converted current in Amperes
 * @return esp_err_t ESP_OK on success
 */
esp_err_t ga700_read_output_current_u1_03(uint16_t *raw_val, float *current_amps);

/**
 * @brief Read full drive telemetry (Status, Freq, Voltage, Current, Faults)
 * @param telem Pointer to telemetry structure to populate
 * @return esp_err_t ESP_OK on success
 */
esp_err_t ga700_read_telemetry(ga700_telemetry_t *telem);

#ifdef __cplusplus
}
#endif

#endif // GA700_MODBUS_H
