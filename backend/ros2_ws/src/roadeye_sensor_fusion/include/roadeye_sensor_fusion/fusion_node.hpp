#ifndef ROADEYE_SENSOR_FUSION__FUSION_NODE_HPP_
#define ROADEYE_SENSOR_FUSION__FUSION_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/float32.hpp>
#include <sensor_msgs/msg/laser_scan.hpp>
#include <roadeye_dashboard_msgs/msg/vehicle_telemetry.hpp>
#include <roadeye_dashboard_msgs/msg/object_detection_array.hpp>
#include <roadeye_dashboard_msgs/msg/lane_state.hpp>

namespace roadeye {
namespace fusion {

class SensorFusionNode : public rclcpp::Node {
public:
  explicit SensorFusionNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());
  ~SensorFusionNode() override = default;

private:
  void initParameters();
  void initSubscribersAndPublishers();
  void fuseAndPublish();

  void onTelemetryReceived(const roadeye_dashboard_msgs::msg::VehicleTelemetry::SharedPtr msg);
  void onObjectsReceived(const roadeye_dashboard_msgs::msg::ObjectDetectionArray::SharedPtr msg);
  void onLidarReceived(const sensor_msgs::msg::LaserScan::SharedPtr msg);
  void onLaneStateReceived(const roadeye_dashboard_msgs::msg::LaneState::SharedPtr msg);

  // Cached sensor data
  roadeye_dashboard_msgs::msg::VehicleTelemetry latest_telem_;
  roadeye_dashboard_msgs::msg::ObjectDetectionArray latest_objects_;
  sensor_msgs::msg::LaserScan latest_scan_;
  roadeye_dashboard_msgs::msg::LaneState latest_lane_;

  bool has_telem_{false};
  bool has_objects_{false};
  bool has_lidar_{false};
  bool has_lane_{false};

  // Config weights
  float weight_camera_{0.4f};
  float weight_lidar_{0.6f};

  rclcpp::Subscription<roadeye_dashboard_msgs::msg::VehicleTelemetry>::SharedPtr sub_telem_;
  rclcpp::Subscription<roadeye_dashboard_msgs::msg::ObjectDetectionArray>::SharedPtr sub_objects_;
  rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr sub_lidar_;
  rclcpp::Subscription<roadeye_dashboard_msgs::msg::LaneState>::SharedPtr sub_lane_;

  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr pub_risk_score_;
  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr pub_ttc_;
  rclcpp::Publisher<roadeye_dashboard_msgs::msg::ObjectDetectionArray>::SharedPtr pub_fused_objects_;

  rclcpp::TimerBase::SharedPtr timer_;
};

}  // namespace fusion
}  // namespace roadeye

#endif  // ROADEYE_SENSOR_FUSION__FUSION_NODE_HPP_
