#ifndef ROADEYE_EMERGENCY__EMERGENCY_NODE_HPP_
#define ROADEYE_EMERGENCY__EMERGENCY_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <roadeye_dashboard_msgs/msg/vehicle_telemetry.hpp>
#include <roadeye_dashboard_msgs/msg/emergency_event.hpp>

#include <queue>
#include <string>

namespace roadeye {
namespace emergency {

class EmergencyNode : public rclcpp::Node {
public:
  explicit EmergencyNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());
  ~EmergencyNode() override = default;

private:
  void initParameters();
  void initSubscribersAndPublishers();
  void checkCrashVerification();
  void processSmsQueue();

  void onImuReceived(const sensor_msgs::msg::Imu::SharedPtr msg);
  void onTelemetryReceived(const roadeye_dashboard_msgs::msg::VehicleTelemetry::SharedPtr msg);

  // Crash verification parameters
  float crash_g_threshold_{4.0f}; // > 4.0g impact
  float sudden_speed_drop_kmh_{30.0f}; // > 30 km/h drop
  std::string emergency_phone_number_{"+919876543210"};

  // Subscriptions & Publishers
  rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr sub_imu_;
  rclcpp::Subscription<roadeye_dashboard_msgs::msg::VehicleTelemetry>::SharedPtr sub_telem_;
  rclcpp::Publisher<roadeye_dashboard_msgs::msg::EmergencyEvent>::SharedPtr pub_emergency_;

  // State cache
  float max_impact_g_{0.0f};
  float previous_speed_kmh_{0.0f};
  float current_speed_kmh_{0.0f};
  double current_lat_{0.0};
  double current_lon_{0.0};

  bool crash_triggered_{false};
  std::queue<roadeye_dashboard_msgs::msg::EmergencyEvent> sms_queue_;

  rclcpp::TimerBase::SharedPtr timer_;
};

}  // namespace emergency
}  // namespace roadeye

#endif  // ROADEYE_EMERGENCY__EMERGENCY_NODE_HPP_
