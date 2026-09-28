# RoadEye — Hardware Wiring & Sensor Hub Schematics

## ESP32 DevKit V1 Pinout Mapping

| Sensor / Module | Interface | ESP32 GPIO Pin | Description |
|---|---|---|---|
| MPU6050 IMU | I2C | GPIO 21 (SDA), GPIO 22 (SCL) | 6-DOF Acceleration & Gyroscope |
| NEO-6M GPS | UART1 | GPIO 4 (RX), GPIO 2 (TX) | NMEA GPS Location |
| TFMini / LD06 LiDAR | UART2 | GPIO 18 (RX), GPIO 19 (TX) | Single-Point / 2D Distance Scan |
| ELM327 OBD-II | Serial / BT | GPIO 16 (RX), GPIO 17 (TX) | Vehicle Speed & Engine RPM |
| SIM800L GSM | SoftwareSerial | GPIO 26 (RX), GPIO 27 (TX) | Emergency SOS SMS Dispatch |

---

## Power Budgeting & Compute Target

- **Compute Target**: Raspberry Pi 5 (8 GB) / Jetson Orin Nano
- **Power Supply**: 5V / 5A DC-DC Buck Converter from vehicle 12V battery port.
- **ESP32 Sensor Hub Power**: Powered via RPi 5 USB port (5V 1A).
