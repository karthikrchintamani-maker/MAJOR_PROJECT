#ifndef SENSOR_HUB_CONFIG_H
#define SENSOR_HUB_CONFIG_H

// WiFi Configuration
#define WIFI_SSID "RoadEye_AP"
#define WIFI_PASS "roadeye2026"
#define RPI5_UDP_IP "192.168.4.1"
#define RPI5_UDP_PORT 8888

// Hardware Pinouts (ESP32 DevKit V1)
#define PIN_OBD_RX 16
#define PIN_OBD_TX 17

#define PIN_GPS_RX 4
#define PIN_GPS_TX 2

#define PIN_LIDAR_RX 18
#define PIN_LIDAR_TX 19

#define PIN_GSM_RX 26
#define PIN_GSM_TX 27

#define MPU6050_SDA 21
#define MPU6050_SCL 22

#endif // SENSOR_HUB_CONFIG_H
