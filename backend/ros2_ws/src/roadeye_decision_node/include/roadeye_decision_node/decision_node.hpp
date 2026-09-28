#ifndef ROADEYE_DECISION_NODE__DECISION_NODE_HPP_
#define ROADEYE_DECISION_NODE__DECISION_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/float32.hpp>
#include <roadeye_dashboard_msgs/msg/warning_alert.hpp>
#include <roadeye_dashboard_msgs/msg/vehicle_telemetry.hpp>
#include <roadeye_dashboard_msgs/msg/lane_state.hpp>
#include <roadeye_dashboard_msgs/msg/pothole_array.hpp>
#include <roadeye_dashboard_msgs/msg/driver_state.hpp>

namespace roadeye {
namespace decision {

class DecisionNode : public rclcpp::Node {
public:
  explicit DecisionNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());
  ~DecisionNode() override = default;

private:
  void initParameters();
  void initSubscribersAndPublishers();
  void evaluateRules();

  // Thresholds
  float fcw_ttc_threshold_sec_{2.5f};
  float aeb_rec_ttc_threshold_sec_{1.2f};
  float ldw_lane_offset_threshold_m_{0.55f};
  float drowsiness_eye_ratio_threshold_{0.40f};
  float speed_limit_kmh_{80.0f};

  // Subscriptions
  rclcpp::Subscription<std_msgs::msg::Float32>::SharedPtr sub_risk_score_;
  rclcpp::Subscription<std_msgs::msg::Float32>::SharedPtr sub_ttc_;
  rclcpp::Subscription<roadeye_dashboard_msgs::msg::VehicleTelemetry>::SharedPtr sub_telem_;
  rclcpp::Subscription<roadeye_dashboard_msgs::msg::LaneState>::SharedPtr sub_lane_;
  rclcpp::Subscription<roadeye_dashboard_msgs::msg::PotholeArray>::SharedPtr sub_potholes_;
  rclcpp::Subscription<roadeye_dashboard_msgs::msg::DriverState>::SharedPtr sub_driver_;

  // Publisher
  rclcpp::Publisher<roadeye_dashboard_msgs::msg::WarningAlert>::SharedPtr pub_warning_;

  // Cache
  float current_risk_score_{0.0f};
  float current_ttc_{999.0f};
  roadeye_dashboard_msgs::msg::VehicleTelemetry latest_telem_;
  roadeye_dashboard_msgs::msg::LaneState latest_lane_;
  roadeye_dashboard_msgs::msg::PotholeArray latest_potholes_;
  roadeye_dashboard_msgs::msg::DriverState latest_driver_;

  rclcpp::TimerBase::SharedPtr timer_;
};

}  // namespace decision
}  // namespace roadeye

#endif  // ROADEYE_DECISION_NODE__DECISION_NODE_HPP_
