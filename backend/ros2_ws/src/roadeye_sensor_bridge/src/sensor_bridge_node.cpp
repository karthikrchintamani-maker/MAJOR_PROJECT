#include "roadeye_sensor_bridge/sensor_bridge_node.hpp"

#include <sys/types.h>
#if defined(_WIN32)
  #include <winsock2.h>
  #include <ws2tcpip.h>
  #pragma comment(lib, "Ws2_32.lib")
#else
  #include <sys/socket.h>
  #include <netinet/in.h>
  #include <unistd.h>
#endif

#include <sstream>
#include <cmath>

namespace roadeye {
namespace bridge {

SensorBridgeNode::SensorBridgeNode(const rclcpp::NodeOptions & options)
: Node("roadeye_sensor_bridge_node", options)
{
  initParameters();
  initPublishers();
  startUdpListener();

  if (use_sim_fallback_) {
    sim_timer_ = this->create_wall_timer(
      std::chrono::milliseconds(50),
      std::bind(&SensorBridgeNode::publishSimulatedData, this));
  }
  RCLCPP_INFO(this->get_logger(), "RoadEye Sensor Bridge Node initialized on UDP port %d", udp_port_);
}

SensorBridgeNode::~SensorBridgeNode() {
  stopUdpListener();
}

void SensorBridgeNode::initParameters() {
  this->declare_parameter("udp_port", 8888);
  this->declare_parameter("use_sim_fallback", true);
  this->declare_parameter("frame_id_base", "base_link");

  udp_port_ = this->get_parameter("udp_port").as_int();
  use_sim_fallback_ = this->get_parameter("use_sim_fallback").as_bool();
  frame_id_base_ = this->get_parameter("frame_id_base").as_string();
}

void SensorBridgeNode::initPublishers() {
  pub_gps_ = this->create_publisher<sensor_msgs::msg::NavSatFix>("/roadeye/sensor/gps", 10);
  pub_imu_ = this->create_publisher<sensor_msgs::msg::Imu>("/roadeye/sensor/imu", 10);
  pub_lidar_ = this->create_publisher<sensor_msgs::msg::LaserScan>("/roadeye/sensor/lidar", 10);
  pub_telemetry_ = this->create_publisher<roadeye_dashboard_msgs::msg::VehicleTelemetry>("/roadeye/vehicle/telemetry", 10);
  pub_health_ = this->create_publisher<roadeye_dashboard_msgs::msg::SensorHealth>("/roadeye/health", 10);
}

void SensorBridgeNode::startUdpListener() {
  running_ = true;
  udp_thread_ = std::thread(&SensorBridgeNode::udpLoop, this);
}

void SensorBridgeNode::stopUdpListener() {
  running_ = false;
  if (udp_thread_.joinable()) {
    udp_thread_.join();
  }
}

void SensorBridgeNode::udpLoop() {
  // Simple non-blocking UDP socket loop for raw JSON telemetry from ESP32
#if defined(_WIN32)
  WSADATA wsaData;
  WSAStartup(MAKEWORD(2, 2), &wsaData);
#endif

  int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
  if (sockfd < 0) {
    RCLCPP_WARN(this->get_logger(), "Failed to create UDP socket.");
    return;
  }

  sockaddr_in server_addr{};
  server_addr.sin_family = AF_INET;
  server_addr.sin_addr.s_addr = INADDR_ANY;
  server_addr.sin_port = htons(static_cast<uint16_t>(udp_port_));

  if (bind(sockfd, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
    RCLCPP_WARN(this->get_logger(), "UDP Bind failed on port %d", udp_port_);
#if defined(_WIN32)
    closesocket(sockfd);
#else
    close(sockfd);
#endif
    return;
  }

  char buffer[1024];
  while (running_ && rclcpp::ok()) {
    sockaddr_in client_addr{};
    socklen_t addr_len = sizeof(client_addr);
    int len = recvfrom(sockfd, buffer, sizeof(buffer) - 1, 0, (struct sockaddr *)&client_addr, &addr_len);
    if (len > 0) {
      buffer[len] = '\0';
      parseAndPublishPacket(std::string(buffer));
    }
  }

#if defined(_WIN32)
  closesocket(sockfd);
  WSACleanup();
#else
  close(sockfd);
#endif
}

void SensorBridgeNode::parseAndPublishPacket(const std::string & payload) {
  // Parse payload (CSV or JSON: speed,rpm,lat,lon,ax,ay,az,lidar)
  std::stringstream ss(payload);
  SensorPacket packet;
  std::string token;
  std::vector<std::string> tokens;
  while (std::getline(ss, token, ',')) {
    tokens.push_back(token);
  }

  if (tokens.size() >= 8) {
    try {
      packet.speed_kmh = std::stof(tokens[0]);
      packet.rpm = std::stof(tokens[1]);
      packet.latitude = std::stod(tokens[2]);
      packet.longitude = std::stod(tokens[3]);
      packet.accel_x = std::stof(tokens[4]);
      packet.accel_y = std::stof(tokens[5]);
      packet.accel_z = std::stof(tokens[6]);
      packet.lidar_dist_m = std::stof(tokens[7]);

      // Publish ROS topics
      auto now = this->now();

      // Telemetry
      roadeye_dashboard_msgs::msg::VehicleTelemetry telem;
      telem.header.stamp = now;
      telem.header.frame_id = frame_id_base_;
      telem.speed_kmh = packet.speed_kmh;
      telem.engine_rpm = packet.rpm;
      telem.latitude = packet.latitude;
      telem.longitude = packet.longitude;
      telem.linear_acceleration.x = packet.accel_x;
      telem.linear_acceleration.y = packet.accel_y;
      telem.linear_acceleration.z = packet.accel_z;
      pub_telemetry_->publish(telem);

    } catch (...) {
      RCLCPP_WARN(this->get_logger(), "Error parsing UDP packet tokens");
    }
  }
}

void SensorBridgeNode::publishSimulatedData() {
  static float t = 0.0f;
  t += 0.05f;

  auto now = this->now();

  // Simulated vehicle telemetry
  roadeye_dashboard_msgs::msg::VehicleTelemetry telem;
  telem.header.stamp = now;
  telem.header.frame_id = frame_id_base_;
  telem.speed_kmh = 45.0f + 5.0f * std::sin(t * 0.5f);
  telem.engine_rpm = 2200.0f + 200.0f * std::sin(t * 0.5f);
  telem.coolant_temp_c = 88.0f;
  telem.battery_voltage = 13.8f;
  telem.latitude = 28.6139 + 0.0001 * std::sin(t * 0.01f); // New Delhi test track
  telem.longitude = 77.2090 + 0.0001 * std::cos(t * 0.01f);
  telem.gps_valid = true;
  telem.gps_satellites = 12;
  telem.linear_acceleration.x = 0.1f * std::cos(t);
  telem.linear_acceleration.y = 0.05f * std::sin(t);
  telem.linear_acceleration.z = 9.81f;
  pub_telemetry_->publish(telem);

  // Simulated GPS fix
  sensor_msgs::msg::NavSatFix gps;
  gps.header.stamp = now;
  gps.header.frame_id = frame_id_gps_;
  gps.latitude = telem.latitude;
  gps.longitude = telem.longitude;
  gps.altitude = 216.0;
  gps.status.status = sensor_msgs::msg::NavSatStatus::STATUS_FIX;
  pub_gps_->publish(gps);

  // Simulated IMU
  sensor_msgs::msg::Imu imu;
  imu.header.stamp = now;
  imu.header.frame_id = frame_id_imu_;
  imu.linear_acceleration = telem.linear_acceleration;
  imu.angular_velocity.z = 0.01f * std::sin(t);
  pub_imu_->publish(imu);

  // Simulated LaserScan LiDAR
  sensor_msgs::msg::LaserScan scan;
  scan.header.stamp = now;
  scan.header.frame_id = frame_id_lidar_;
  scan.angle_min = -0.5f;
  scan.angle_max = 0.5f;
  scan.angle_increment = 0.01f;
  scan.range_min = 0.1f;
  scan.range_max = 12.0f;
  size_t num_ranges = static_cast<size_t>((scan.angle_max - scan.angle_min) / scan.angle_increment);
  float sim_dist = 8.5f + 2.0f * std::sin(t * 0.3f);
  scan.ranges.assign(num_ranges, sim_dist);
  pub_lidar_->publish(scan);

  // Sensor Health
  roadeye_dashboard_msgs::msg::SensorHealth health;
  health.header.stamp = now;
  health.camera_ok = true;
  health.lidar_ok = true;
  health.gps_ok = true;
  health.imu_ok = true;
  health.obd_ok = true;
  health.gsm_ok = true;
  health.camera_fps = 25.0f;
  health.lidar_hz = 20.0f;
  health.system_load_pct = 32.5f;
  health.temperature_c = 44.0f;
  health.status_message = "All Sensor Hub Systems Operational";
  pub_health_->publish(health);
}

}  // namespace bridge
}  // namespace roadeye
