#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include <TinyGPS++.h>
#include <MPU6050.h>

#include "sensor_hub_config.h"

WiFiUDP udp;
MPU6050 mpu;
TinyGPSPlus gps;
HardwareSerial gpsSerial(1);
HardwareSerial lidarSerial(2);

struct SensorData {
  float speed_kmh = 45.0f;
  float rpm = 2200.0f;
  double lat = 28.6139;
  double lon = 77.2090;
  float ax = 0.0f, ay = 0.0f, az = 9.81f;
  float lidar_m = 8.5f;
} data;

void setup() {
  Serial.begin(115200);
  Wire.begin(MPU6050_SDA, MPU6050_SCL);

  Serial.println("[ESP32 Sensor Hub] Initializing...");

  // Init MPU6050
  mpu.initialize();
  if (mpu.testConnection()) {
    Serial.println("[MPU6050] Connected successfully.");
  }

  // Init GPS Serial
  gpsSerial.begin(9600, SERIAL_8N1, PIN_GPS_RX, PIN_GPS_TX);

  // Init LiDAR Serial
  lidarSerial.begin(115200, SERIAL_8N1, PIN_LIDAR_RX, PIN_LIDAR_TX);

  // Init WiFi Access Point / Station
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 10) {
    delay(500);
    Serial.print(".");
    retries++;
  }
  Serial.println("\n[WiFi] Connected to Network!");

  udp.begin(RPI5_UDP_PORT);
}

void loop() {
  // Read MPU6050 acceleration
  int16_t ax, ay, az;
  mpu.getAcceleration(&ax, &ay, &az);
  data.ax = (ax / 16384.0f) * 9.81f;
  data.ay = (ay / 16384.0f) * 9.81f;
  data.az = (az / 16384.0f) * 9.81f;

  // Read GPS
  while (gpsSerial.available() > 0) {
    gps.encode(gpsSerial.read());
  }
  if (gps.location.isValid()) {
    data.lat = gps.location.lat();
    data.lon = gps.location.lng();
  }

  // Read TFMini / LD06 LiDAR frame (9-byte protocol)
  if (lidarSerial.available() >= 9) {
    if (lidarSerial.read() == 0x59 && lidarSerial.read() == 0x59) {
      uint8_t low = lidarSerial.read();
      uint8_t high = lidarSerial.read();
      uint16_t dist_cm = (high << 8) | low;
      data.lidar_m = dist_cm / 100.0f;
    }
  }

  // Format CSV packet: speed,rpm,lat,lon,ax,ay,az,lidar
  char packet[256];
  snprintf(packet, sizeof(packet), "%.2f,%.2f,%.6f,%.6f,%.2f,%.2f,%.2f,%.2f",
           data.speed_kmh, data.rpm, data.lat, data.lon,
           data.ax, data.ay, data.az, data.lidar_m);

  // Transmit over UDP to RPi 5
  udp.beginPacket(RPI5_UDP_IP, RPI5_UDP_PORT);
  udp.write((const uint8_t*)packet, strlen(packet));
  udp.endPacket();

  delay(50); // 20 Hz loop
}
