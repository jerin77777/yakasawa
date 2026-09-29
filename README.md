# Industrial ESP32-S3 RS-485 Control Program for Yaskawa GA700 VFD

This project is a complete, production-ready **ESP-IDF** (C) program designed to run on the **Industrial ESP32-S3 Control Board** (Waveshare / Robu.in) to control and monitor a **Yaskawa GA700 Variable Frequency Drive (VFD)** over **RS-485 (MEMOBUS / Modbus RTU)**.

---

## 📌 Board & Hardware Features

- **Microcontroller**: ESP32-S3 (Dual-core 240 MHz, Wi-Fi & Bluetooth 5)
- **Onboard Isolated RS-485**: Direct screw terminals (`A+`, `B-`, `GND`) with built-in hardware direction control.
- **Yaskawa GA700 Control**:
  - Run Forward / Run Reverse / Stop control
  - High-precision Frequency Reference setting (0.01 Hz resolution)
  - Fault Reset command execution
  - Real-time telemetry monitoring (Frequency, Voltage, Current, DC Bus Voltage, Torque, Fault/Alarm codes)
- **Non-blocking FreeRTOS Polling**: Telemetry monitor runs in a background task every 1 second.

---

## 🔌 Hardware Wiring & Pin Mapping

### 1. Board Onboard Hardware GPIOs

| Signal / Function | ESP32-S3 Internal Pin | Board Terminal / Component |
|-------------------|-----------------------|----------------------------|
| **RS485 TX**      | **GPIO 17**           | Built-in RS485 Driver TX   |
| **RS485 RX**      | **GPIO 18**           | Built-in RS485 Driver RX   |
| **RS485 EN (RTS)**| **GPIO 21**           | Built-in Hardware Direction Control |
| **Data+**         | N/A                   | **A+** Screw Terminal      |
| **Data-**         | N/A                   | **B-** Screw Terminal      |
| **Ground**        | N/A                   | **GND** Screw Terminal     |

### 2. Screw Terminal Wiring to Yaskawa GA700 VFD

| Industrial ESP32-S3 Terminal | Yaskawa GA700 Terminal | Description |
|------------------------------|------------------------|-------------|
| **A+**                       | **R+** and **S+** *(Jumpered)* | RS-485 Data + (Non-inverting) |
| **B-**                       | **R-** and **S-** *(Jumpered)* | RS-485 Data - (Inverting) |
| **GND**                      | **IG** or Shield Ground | Cable Shield & Common Ground |

> 💡 **Termination Resistor Jumper**: The Industrial ESP32-S3 board has an onboard 120 Ω termination resistor. Set the **RS-485 120Ω Jumper** to **ON** (closed).

---

## ⚙️ Yaskawa GA700 Drive Parameter Setup

Configure the following parameters on the **GA700 Keypad**:

| Parameter | Setting Name | Required Value | Description |
|-----------|--------------|----------------|-------------|
| `b1-01` | Frequency Reference Source 1 | **2** | MEMOBUS / Modbus RS-485 |
| `b1-02` | Run Command Source 1 | **2** | MEMOBUS / Modbus RS-485 |
| `H5-01` | Drive Slave Address | **1F** (31 decimal) | Modbus Node ID (Matches code) |
| `H5-02` | Baud Rate Selection | **3** (9600 bps) | `0`=1200, `1`=2400, `2`=4800, `3`=9600, `4`=19200, `5`=38400, `6`=57600, `7`=115200 |
| `H5-03` | Communication Parity | **0** (No Parity) | `0`=No Parity (8-N-1), `1`=Even, `2`=Odd |
| `H5-04` | Stopping Method on Comm Error | **1** (Ramp Stop) | `0`=Alarm & Cont, `1`=Ramp Stop, `2`=Coast, `3`=Fast Stop |
| `H5-07` | RTS Control Selection | **1** (Enabled) | Hardware RTS Flow Control |

---

## ⚡ Flashing via `pnpm` Shortcuts

You can now use `pnpm` shortcuts to set up, build, flash, and monitor your board:

```bash
# 1. Set the chip target to ESP32-S3 (run once)
pnpm run set-target

# 2. Build the project
pnpm run build

# 3. Flash to board and start real-time monitor automatically
pnpm run flash

# 4. Flash specifying a specific COM port (e.g. COM5)
pnpm run flash -- -p COM5

# 5. Open monitor only
pnpm run monitor

# 6. Clean build artifacts
pnpm run clean
```

---

## ⚡ Manual ESP-IDF Terminal Instructions

Follow these steps to compile and flash the program into the **Industrial ESP32-S3 Control Board**:

### Step 1: Prerequisites
- Install **ESP-IDF** (v4.4, v5.0, or higher) on your computer.
- Connect the **Industrial ESP32-S3 Control Board** to your PC using a **USB Type-C** data cable.

---

### Step 2: Open ESP-IDF Terminal
- On Windows, launch **ESP-IDF 5.x CMD** or **ESP-IDF 5.x PowerShell** from the Start Menu.
- Alternatively, open standard PowerShell and run your ESP-IDF export script:
  ```powershell
  C:\esp-idf\export.ps1
  ```

---

### Step 3: Navigate to Workspace Directory
```bash
cd c:\Users\jerin\Music\yakasawa
```

---

### Step 4: Set ESP32-S3 Chip Target
Set the build target to ESP32-S3:
```bash
idf.py set-target esp32s3
```

---

### Step 5: Identify COM Port
1. Open Windows **Device Manager** (`Win + X` ➔ `Device Manager`).
2. Expand **Ports (COM & LPT)**.
3. Look for your board connection (e.g., **Silicon Labs CP210x**, **CH340**, or **USB Serial Device**).
4. Note the COM port number (e.g., `COM3`, `COM5`, `COM7`).

---

### Step 6: Build the Project
Compile the code:
```bash
idf.py build
```
*Wait for compilation to complete. You should see `Project build complete.`*

---

### Step 7: Flash to Board & Open Monitor
Flash the firmware and automatically start the real-time serial monitor (Replace `COMx` with your actual COM port, e.g., `COM5`):

```bash
idf.py -p COM5 flash monitor
```

---

### 🆘 Manual Bootloader Mode (If Auto-Flash Fails)

If `idf.py flash` reports `A fatal error occurred: Failed to connect to ESP32-S3`, put the board into manual Download Mode:

1. Press and **HOLD** the **BOOT** button on the Industrial ESP32-S3 board.
2. Press the **RESET (RST)** button once.
3. **RELEASE** the **BOOT** button.
4. Run the flash command again:
   ```bash
   idf.py -p COM5 flash monitor
   ```
5. Press the **RESET (RST)** button once after flashing finishes to start normal operation.

> 💡 **To Exit Serial Monitor**: Press `Ctrl + ]` on your keyboard.

---

## 📖 Yaskawa GA700 Modbus Register Map

| Register (HEX) | Register (DEC) | Function Code | Description & Format |
|----------------|----------------|---------------|----------------------|
| `0x0001` | 1 | 0x06 (Write) | **Operation Command**:<br>• Bit 0: Run (1) / Stop (0)<br>• Bit 1: Reverse (1) / Forward (0)<br>• Bit 3: Fault Reset (1) |
| `0x0002` | 2 | 0x06 (Write) | **Frequency Reference**: 0.01 Hz resolution (e.g., `5000` = 50.00 Hz) |
| `0x0020` | 32 | 0x03 (Read) | **Drive Status 1**:<br>• Bit 0: Running<br>• Bit 2: Reverse<br>• Bit 4: Speed Agree<br>• Bit 5: Drive Ready<br>• Bit 7: Major Fault |
| `0x0021` | 33 | 0x03 (Read) | **Fault Contents**: Active Fault Code |
| `0x0022` | 34 | 0x03 (Read) | **Alarm Contents**: Active Alarm Code |
| `0x0024` | 36 | 0x03 (Read) | **Output Frequency**: 0.01 Hz resolution |
| `0x0025` | 37 | 0x03 (Read) | **Output Voltage**: 0.1 V resolution |
| `0x0026` | 38 | 0x03 (Read) | **Output Current**: 0.1 A resolution |
| `0x0027` | 39 | 0x03 (Read) | **Output Power**: 0.1 kW resolution |
| `0x0028` | 40 | 0x03 (Read) | **DC Bus Voltage**: 1 V resolution |
| `0x002B` | 43 | 0x03 (Read) | **Output Torque**: 0.1 % resolution |

---

## 💻 Sample Log Output in Serial Monitor

When running, `idf.py monitor` will display output like this:

```
I (512) APP_MAIN: ==================================================
I (522) APP_MAIN:  ESP32-S3 Yaskawa GA700 RS-485 Modbus Controller
I (532) APP_MAIN: ==================================================
I (542) GA700_MODBUS: Initializing RS-485 UART2 [TX:17, RX:18, RTS/DE:21] Baud:9600 Parity:1 SlaveID:1
I (552) GA700_MODBUS: RS-485 driver successfully initialized for Yaskawa GA700
I (562) APP_MAIN: VFD Monitor Task Started
I (1572) APP_MAIN: --------------------------------------------------
I (1582) APP_MAIN: Status: [Run: STOPPED | Dir: FWD | Ready: YES | Agreed: NO | Fault: NORMAL]
I (1592) APP_MAIN: Metrics: Freq: 0.00 Hz | Volt: 0.0 V | Curr: 0.0 A | DC Bus: 560 V | Torque: 0.0 %
I (4572) APP_MAIN: [DEMO STEP 1] Setting Frequency Reference to 25.00 Hz...
I (4582) GA700_MODBUS: Setting Frequency Reference: 25.00 Hz (Raw: 2500)
I (5572) APP_MAIN: [DEMO STEP 2] Starting Motor FORWARD...
I (5582) GA700_MODBUS: Sending Command: RUN FORWARD
```
