#ifndef ROADEYE_SENSOR_BRIDGE__SENSOR_BRIDGE_NODE_HPP_
#define ROADEYE_SENSOR_BRIDGE__SENSOR_BRIDGE_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/nav_sat_fix.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <sensor_msgs/msg/laser_scan.hpp>
#include <roadeye_dashboard_msgs/msg/vehicle_telemetry.hpp>
#include <roadeye_dashboard_msgs/msg/sensor_health.hpp>

#include <thread>
#include <atomic>
#include <mutex>
#include <string>

namespace roadeye {
namespace bridge {

struct SensorPacket {
  float speed_kmh{0.0f};
  float rpm{0.0f};
  float coolant_temp{0.0f};
  double latitude{0.0};
  double longitude{0.0};
  float gps_speed_kmh{0.0f};
  float accel_x{0.0f}, accel_y{0.0f}, accel_z{0.0f};
  float gyro_x{0.0f}, gyro_y{0.0f}, gyro_z{0.0f};
  float lidar_dist_m{0.0f};
  bool obd_ok{true};
  bool gps_ok{true};
  bool imu_ok{true};
  bool lidar_ok{true};
};

class SensorBridgeNode : public rclcpp::Node {
public:
  explicit SensorBridgeNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());
  ~SensorBridgeNode() override;

private:
  void initParameters();
  void initPublishers();
  void startUdpListener();
  void stopUdpListener();
  void udpLoop();
  void parseAndPublishPacket(const std::string & payload);

  int udp_port_{8888};
  std::string frame_id_base_{"base_link"};
  std::string frame_id_gps_{"gps_link"};
  std::string frame_id_imu_{"imu_link"};
  std::string frame_id_lidar_{"lidar_link"};

  rclcpp::Publisher<sensor_msgs::msg::NavSatFix>::SharedPtr pub_gps_;
  rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr pub_imu_;
  rclcpp::Publisher<sensor_msgs::msg::LaserScan>::SharedPtr pub_lidar_;
  rclcpp::Publisher<roadeye_dashboard_msgs::msg::VehicleTelemetry>::SharedPtr pub_telemetry_;
  rclcpp::Publisher<roadeye_dashboard_msgs::msg::SensorHealth>::SharedPtr pub_health_;

  std::thread udp_thread_;
  std::atomic<bool> running_{false};
  std::mutex data_mutex_;

  // Simulation mode fallback timer when hardware disconnected
  rclcpp::TimerBase::SharedPtr sim_timer_;
  bool use_sim_fallback_{true};
  void publishSimulatedData();
};

}  // namespace bridge
}  // namespace roadeye

#endif  // ROADEYE_SENSOR_BRIDGE__SENSOR_BRIDGE_NODE_HPP_
