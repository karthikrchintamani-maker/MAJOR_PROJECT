#ifndef ROADEYE_VEHICLE_INTERFACE__VEHICLE_INTERFACE_NODE_HPP_
#define ROADEYE_VEHICLE_INTERFACE__VEHICLE_INTERFACE_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist_stamped.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <tf2_ros/transform_broadcaster.h>
#include <tf2_ros/static_transform_broadcaster.h>
#include <roadeye_dashboard_msgs/msg/vehicle_telemetry.hpp>

namespace roadeye {
namespace vehicle {

class VehicleInterfaceNode : public rclcpp::Node {
public:
  explicit VehicleInterfaceNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());
  ~VehicleInterfaceNode() override = default;

private:
  void initParameters();
  void initBroadcastersAndPublishers();
  void publishStaticTransforms();
  void onTelemetryReceived(const roadeye_dashboard_msgs::msg::VehicleTelemetry::SharedPtr msg);

  rclcpp::Subscription<roadeye_dashboard_msgs::msg::VehicleTelemetry>::SharedPtr sub_telem_;
  rclcpp::Publisher<geometry_msgs::msg::TwistStamped>::SharedPtr pub_velocity_status_;
  rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr pub_odometry_;

  std::unique_ptr<tf2_ros::TransformBroadcaster> tf_broadcaster_;
  std::shared_ptr<tf2_ros::StaticTransformBroadcaster> static_tf_broadcaster_;
};

}  // namespace vehicle
}  // namespace roadeye

#endif  // ROADEYE_VEHICLE_INTERFACE__VEHICLE_INTERFACE_NODE_HPP_
