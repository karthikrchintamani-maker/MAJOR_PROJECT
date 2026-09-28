#include "roadeye_sensor_fusion/fusion_node.hpp"
#include "roadeye_utils/math_utils.hpp"
#include <algorithm>

namespace roadeye {
namespace fusion {

SensorFusionNode::SensorFusionNode(const rclcpp::NodeOptions & options)
: Node("roadeye_sensor_fusion_node", options)
{
  initParameters();
  initSubscribersAndPublishers();

  timer_ = this->create_wall_timer(
    std::chrono::milliseconds(50), // 20 Hz fusion loop
    std::bind(&SensorFusionNode::fuseAndPublish, this));

  RCLCPP_INFO(this->get_logger(), "RoadEye Sensor Fusion Node started at 20 Hz.");
}

void SensorFusionNode::initParameters() {
  this->declare_parameter("weight_camera", 0.4f);
  this->declare_parameter("weight_lidar", 0.6f);

  weight_camera_ = static_cast<float>(this->get_parameter("weight_camera").as_double());
  weight_lidar_ = static_cast<float>(this->get_parameter("weight_lidar").as_double());
}

void SensorFusionNode::initSubscribersAndPublishers() {
  sub_telem_ = this->create_subscription<roadeye_dashboard_msgs::msg::VehicleTelemetry>(
    "/roadeye/vehicle/telemetry", 10,
    std::bind(&SensorFusionNode::onTelemetryReceived, this, std::placeholders::_1));

  sub_objects_ = this->create_subscription<roadeye_dashboard_msgs::msg::ObjectDetectionArray>(
    "/roadeye/perception/objects", 10,
    std::bind(&SensorFusionNode::onObjectsReceived, this, std::placeholders::_1));

  sub_lidar_ = this->create_subscription<sensor_msgs::msg::LaserScan>(
    "/roadeye/sensor/lidar", 10,
    std::bind(&SensorFusionNode::onLidarReceived, this, std::placeholders::_1));

  sub_lane_ = this->create_subscription<roadeye_dashboard_msgs::msg::LaneState>(
    "/roadeye/perception/lane_state", 10,
    std::bind(&SensorFusionNode::onLaneStateReceived, this, std::placeholders::_1));

  pub_risk_score_ = this->create_publisher<std_msgs::msg::Float32>("/roadeye/fusion/risk_score", 10);
  pub_ttc_ = this->create_publisher<std_msgs::msg::Float32>("/roadeye/fusion/ttc", 10);
  pub_fused_objects_ = this->create_publisher<roadeye_dashboard_msgs::msg::ObjectDetectionArray>("/roadeye/fusion/fused_objects", 10);
}

void SensorFusionNode::onTelemetryReceived(const roadeye_dashboard_msgs::msg::VehicleTelemetry::SharedPtr msg) {
  latest_telem_ = *msg;
  has_telem_ = true;
}

void SensorFusionNode::onObjectsReceived(const roadeye_dashboard_msgs::msg::ObjectDetectionArray::SharedPtr msg) {
  latest_objects_ = *msg;
  has_objects_ = true;
}

void SensorFusionNode::onLidarReceived(const sensor_msgs::msg::LaserScan::SharedPtr msg) {
  latest_scan_ = *msg;
  has_lidar_ = true;
}

void SensorFusionNode::onLaneStateReceived(const roadeye_dashboard_msgs::msg::LaneState::SharedPtr msg) {
  latest_lane_ = *msg;
  has_lane_ = true;
}

void SensorFusionNode::fuseAndPublish() {
  float min_target_dist = 999.0f;
  float min_ttc = 999.0f;

  // Extract min LiDAR distance in front cone
  if (has_lidar_ && !latest_scan_.ranges.empty()) {
    for (float r : latest_scan_.ranges) {
      if (r > latest_scan_.range_min && r < latest_scan_.range_max) {
        min_target_dist = std::min(min_target_dist, r);
      }
    }
  }

  // Fuse camera detections with LiDAR distance
  roadeye_dashboard_msgs::msg::ObjectDetectionArray fused_arr;
  fused_arr.header.stamp = this->now();

  if (has_objects_) {
    for (auto det : latest_objects_.detections) {
      // EKF / weighted spatial fusion of camera depth estimate and LiDAR range
      float cam_dist = det.distance_m;
      float fused_dist = (min_target_dist < 50.0f) ?
        (weight_camera_ * cam_dist + weight_lidar_ * min_target_dist) : cam_dist;

      det.distance_m = fused_dist;
      det.position.x = fused_dist;

      float v_rel_ms = (has_telem_) ? (latest_telem_.speed_kmh / 3.6f) : 10.0f;
      det.ttc_sec = utils::MathUtils::calculateTTC(fused_dist, v_rel_ms);

      fused_arr.detections.push_back(det);
      min_ttc = std::min(min_ttc, det.ttc_sec);
    }
  }

  float current_speed = has_telem_ ? latest_telem_.speed_kmh : 50.0f;
  float lane_offset = has_lane_ ? latest_lane_.center_offset : 0.0f;

  float risk_score = utils::MathUtils::calculateRiskScore(
    min_ttc, min_target_dist, current_speed, lane_offset);

  std_msgs::msg::Float32 risk_msg;
  risk_msg.data = risk_score;
  pub_risk_score_->publish(risk_msg);

  std_msgs::msg::Float32 ttc_msg;
  ttc_msg.data = min_ttc;
  pub_ttc_->publish(ttc_msg);

  pub_fused_objects_->publish(fused_arr);
}

}  // namespace fusion
}  // namespace roadeye
