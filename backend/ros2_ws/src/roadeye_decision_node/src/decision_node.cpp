#include "roadeye_decision_node/decision_node.hpp"

namespace roadeye {
namespace decision {

DecisionNode::DecisionNode(const rclcpp::NodeOptions & options)
: Node("roadeye_decision_node", options)
{
  initParameters();
  initSubscribersAndPublishers();

  timer_ = this->create_wall_timer(
    std::chrono::milliseconds(50), // 20 Hz rule evaluation
    std::bind(&DecisionNode::evaluateRules, this));

  RCLCPP_INFO(this->get_logger(), "RoadEye Safety Decision Node started at 20 Hz.");
}

void DecisionNode::initParameters() {
  this->declare_parameter("fcw_ttc_threshold_sec", 2.5f);
  this->declare_parameter("aeb_rec_ttc_threshold_sec", 1.2f);
  this->declare_parameter("ldw_lane_offset_threshold_m", 0.55f);
  this->declare_parameter("drowsiness_eye_ratio_threshold", 0.40f);
  this->declare_parameter("speed_limit_kmh", 80.0f);

  fcw_ttc_threshold_sec_ = static_cast<float>(this->get_parameter("fcw_ttc_threshold_sec").as_double());
  aeb_rec_ttc_threshold_sec_ = static_cast<float>(this->get_parameter("aeb_rec_ttc_threshold_sec").as_double());
  ldw_lane_offset_threshold_m_ = static_cast<float>(this->get_parameter("ldw_lane_offset_threshold_m").as_double());
  drowsiness_eye_ratio_threshold_ = static_cast<float>(this->get_parameter("drowsiness_eye_ratio_threshold").as_double());
  speed_limit_kmh_ = static_cast<float>(this->get_parameter("speed_limit_kmh").as_double());
}

void DecisionNode::initSubscribersAndPublishers() {
  sub_risk_score_ = this->create_subscription<std_msgs::msg::Float32>(
    "/roadeye/fusion/risk_score", 10,
    [this](const std_msgs::msg::Float32::SharedPtr msg) { current_risk_score_ = msg->data; });

  sub_ttc_ = this->create_subscription<std_msgs::msg::Float32>(
    "/roadeye/fusion/ttc", 10,
    [this](const std_msgs::msg::Float32::SharedPtr msg) { current_ttc_ = msg->data; });

  sub_telem_ = this->create_subscription<roadeye_dashboard_msgs::msg::VehicleTelemetry>(
    "/roadeye/vehicle/telemetry", 10,
    [this](const roadeye_dashboard_msgs::msg::VehicleTelemetry::SharedPtr msg) { latest_telem_ = *msg; });

  sub_lane_ = this->create_subscription<roadeye_dashboard_msgs::msg::LaneState>(
    "/roadeye/perception/lane_state", 10,
    [this](const roadeye_dashboard_msgs::msg::LaneState::SharedPtr msg) { latest_lane_ = *msg; });

  sub_potholes_ = this->create_subscription<roadeye_dashboard_msgs::msg::PotholeArray>(
    "/roadeye/perception/potholes", 10,
    [this](const roadeye_dashboard_msgs::msg::PotholeArray::SharedPtr msg) { latest_potholes_ = *msg; });

  sub_driver_ = this->create_subscription<roadeye_dashboard_msgs::msg::DriverState>(
    "/roadeye/perception/driver_state", 10,
    [this](const roadeye_dashboard_msgs::msg::DriverState::SharedPtr msg) { latest_driver_ = *msg; });

  pub_warning_ = this->create_publisher<roadeye_dashboard_msgs::msg::WarningAlert>("/roadeye/warnings", 10);
}

void DecisionNode::evaluateRules() {
  roadeye_dashboard_msgs::msg::WarningAlert alert;
  alert.header.stamp = this->now();
  alert.header.frame_id = "base_link";
  alert.current_speed = latest_telem_.speed_kmh;
  alert.time_to_collision = current_ttc_;
  alert.alert_type = roadeye_dashboard_msgs::msg::WarningAlert::ALERT_NONE;
  alert.severity = 1;

  // Rule 1: AEB Recommendation (Critical TTC < 1.2s)
  if (current_ttc_ > 0.0f && current_ttc_ <= aeb_rec_ttc_threshold_sec_) {
    alert.alert_type = roadeye_dashboard_msgs::msg::WarningAlert::AEB_RECOMMENDATION;
    alert.severity = 4; // CRITICAL
    alert.message = "CRITICAL: EMERGENCY BRAKING RECOMMENDED!";
    alert.audio_trigger = true;
    alert.haptic_trigger = true;
  }
  // Rule 2: Forward Collision Warning (FCW TTC < 2.5s)
  else if (current_ttc_ > 0.0f && current_ttc_ <= fcw_ttc_threshold_sec_) {
    alert.alert_type = roadeye_dashboard_msgs::msg::WarningAlert::FCW;
    alert.severity = 3; // HIGH
    alert.message = "WARNING: FORWARD COLLISION RISK!";
    alert.audio_trigger = true;
  }
  // Rule 3: Lane Departure Warning (LDW)
  else if (latest_lane_.lane_departure_left || latest_lane_.center_offset < -ldw_lane_offset_threshold_m_) {
    alert.alert_type = roadeye_dashboard_msgs::msg::WarningAlert::LDW_LEFT;
    alert.severity = 2; // MEDIUM
    alert.message = "LANE DEPARTURE ALERT: LEFT DEVIATION";
    alert.audio_trigger = true;
  }
  else if (latest_lane_.lane_departure_right || latest_lane_.center_offset > ldw_lane_offset_threshold_m_) {
    alert.alert_type = roadeye_dashboard_msgs::msg::WarningAlert::LDW_RIGHT;
    alert.severity = 2; // MEDIUM
    alert.message = "LANE DEPARTURE ALERT: RIGHT DEVIATION";
    alert.audio_trigger = true;
  }
  // Rule 4: Pothole Advisory
  else if (!latest_potholes_.potholes.empty()) {
    alert.alert_type = roadeye_dashboard_msgs::msg::WarningAlert::POTHOLE_AHEAD;
    alert.severity = 2; // MEDIUM
    alert.message = "POTHOLE AHEAD - SLOW DOWN";
    alert.distance_to_target = latest_potholes_.potholes[0].distance_m;
    alert.audio_trigger = false;
  }
  // Rule 5: Driver Drowsiness Alert
  else if (latest_driver_.is_drowsy || latest_driver_.eye_closure_ratio > drowsiness_eye_ratio_threshold_) {
    alert.alert_type = roadeye_dashboard_msgs::msg::WarningAlert::DROWSINESS_WARNING;
    alert.severity = 3; // HIGH
    alert.message = "DRIVER DROWSINESS DETECTED - TAKE A BREAK!";
    alert.audio_trigger = true;
  }
  // Rule 6: Speeding Warning
  else if (latest_telem_.speed_kmh > speed_limit_kmh_) {
    alert.alert_type = roadeye_dashboard_msgs::msg::WarningAlert::SPEEDING_WARNING;
    alert.severity = 2; // MEDIUM
    alert.message = "SPEEDING WARNING: EXCEEDED ROAD LIMIT";
    alert.audio_trigger = true;
  }

  pub_warning_->publish(alert);
}

}  // namespace decision
}  // namespace roadeye
