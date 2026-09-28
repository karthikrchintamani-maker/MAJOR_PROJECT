#include "roadeye_vehicle_interface/vehicle_interface_node.hpp"
#include <geometry_msgs/msg/transform_stamped.hpp>

namespace roadeye {
namespace vehicle {

VehicleInterfaceNode::VehicleInterfaceNode(const rclcpp::NodeOptions & options)
: Node("roadeye_vehicle_interface_node", options)
{
  initParameters();
  initBroadcastersAndPublishers();
  publishStaticTransforms();

  RCLCPP_INFO(this->get_logger(), "RoadEye Autoware Interoperability Vehicle Interface Started.");
}

void VehicleInterfaceNode::initParameters() {
}

void VehicleInterfaceNode::initBroadcastersAndPublishers() {
  sub_telem_ = this->create_subscription<roadeye_dashboard_msgs::msg::VehicleTelemetry>(
    "/roadeye/vehicle/telemetry", 10,
    std::bind(&VehicleInterfaceNode::onTelemetryReceived, this, std::placeholders::_1));

  pub_velocity_status_ = this->create_publisher<geometry_msgs::msg::TwistStamped>(
    "/vehicle/status/velocity_status", 10);

  pub_odometry_ = this->create_publisher<nav_msgs::msg::Odometry>(
    "/localization/kinematic_state", 10);

  tf_broadcaster_ = std::make_unique<tf2_ros::TransformBroadcaster>(*this);
  static_tf_broadcaster_ = std::make_shared<tf2_ros::StaticTransformBroadcaster>(this);
}

void VehicleInterfaceNode::publishStaticTransforms() {
  auto now = this->now();
  std::vector<geometry_msgs::msg::TransformStamped> transforms;

  // base_link -> camera_link
  geometry_msgs::msg::TransformStamped tf_cam;
  tf_cam.header.stamp = now;
  tf_cam.header.frame_id = "base_link";
  tf_cam.child_frame_id = "camera_link";
  tf_cam.transform.translation.x = 1.5; // 1.5m in front of rear axle
  tf_cam.transform.translation.y = 0.0;
  tf_cam.transform.translation.z = 1.2; // 1.2m height
  tf_cam.transform.rotation.w = 1.0;
  transforms.push_back(tf_cam);

  // base_link -> lidar_link
  geometry_msgs::msg::TransformStamped tf_lidar;
  tf_lidar.header.stamp = now;
  tf_lidar.header.frame_id = "base_link";
  tf_lidar.child_frame_id = "lidar_link";
  tf_lidar.transform.translation.x = 1.8; // Front bumper
  tf_lidar.transform.translation.y = 0.0;
  tf_lidar.transform.translation.z = 0.4; // Low bumper height
  tf_lidar.transform.rotation.w = 1.0;
  transforms.push_back(tf_lidar);

  // base_link -> imu_link
  geometry_msgs::msg::TransformStamped tf_imu;
  tf_imu.header.stamp = now;
  tf_imu.header.frame_id = "base_link";
  tf_imu.child_frame_id = "imu_link";
  tf_imu.transform.translation.x = 0.5;
  tf_imu.transform.translation.y = 0.0;
  tf_imu.transform.translation.z = 0.3;
  tf_imu.transform.rotation.w = 1.0;
  transforms.push_back(tf_imu);

  static_tf_broadcaster_->sendTransform(transforms);
}

void VehicleInterfaceNode::onTelemetryReceived(const roadeye_dashboard_msgs::msg::VehicleTelemetry::SharedPtr msg) {
  auto now = msg->header.stamp;
  float speed_ms = msg->speed_kmh / 3.6f;

  // 1. Publish Autoware velocity_status topic
  geometry_msgs::msg::TwistStamped twist;
  twist.header.stamp = now;
  twist.header.frame_id = "base_link";
  twist.twist.linear.x = speed_ms;
  twist.twist.angular = msg->angular_velocity;
  pub_velocity_status_->publish(twist);

  // 2. Publish Autoware localization kinematic state topic
  nav_msgs::msg::Odometry odom;
  odom.header.stamp = now;
  odom.header.frame_id = "odom";
  odom.child_frame_id = "base_link";
  odom.twist.twist = twist.twist;
  pub_odometry_->publish(odom);

  // 3. Broadcast dynamic odom -> base_link transform
  geometry_msgs::msg::TransformStamped tf_odom;
  tf_odom.header.stamp = now;
  tf_odom.header.frame_id = "odom";
  tf_odom.child_frame_id = "base_link";
  tf_odom.transform.translation.x = 0.0;
  tf_odom.transform.translation.y = 0.0;
  tf_odom.transform.translation.z = 0.0;
  tf_odom.transform.rotation.w = 1.0;
  tf_broadcaster_->sendTransform(tf_odom);
}

}  // namespace vehicle
}  // namespace roadeye
