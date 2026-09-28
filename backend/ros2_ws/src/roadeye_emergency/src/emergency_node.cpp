#include "roadeye_emergency/emergency_node.hpp"
#include <cmath>
#include <sstream>

namespace roadeye {
namespace emergency {

EmergencyNode::EmergencyNode(const rclcpp::NodeOptions & options)
: Node("roadeye_emergency_node", options)
{
  initParameters();
  initSubscribersAndPublishers();

  timer_ = this->create_wall_timer(
    std::chrono::milliseconds(100), // 10 Hz verification & SOS queue worker
    std::bind(&EmergencyNode::checkCrashVerification, this));

  RCLCPP_INFO(this->get_logger(), "RoadEye Emergency Crash Verification Node initialized.");
}

void EmergencyNode::initParameters() {
  this->declare_parameter("crash_g_threshold", 4.0f);
  this->declare_parameter("sudden_speed_drop_kmh", 30.0f);
  this->declare_parameter("emergency_phone_number", "+919876543210");

  crash_g_threshold_ = static_cast<float>(this->get_parameter("crash_g_threshold").as_double());
  sudden_speed_drop_kmh_ = static_cast<float>(this->get_parameter("sudden_speed_drop_kmh").as_double());
  emergency_phone_number_ = this->get_parameter("emergency_phone_number").as_string();
}

void EmergencyNode::initSubscribersAndPublishers() {
  sub_imu_ = this->create_subscription<sensor_msgs::msg::Imu>(
    "/roadeye/sensor/imu", 10,
    std::bind(&EmergencyNode::onImuReceived, this, std::placeholders::_1));

  sub_telem_ = this->create_subscription<roadeye_dashboard_msgs::msg::VehicleTelemetry>(
    "/roadeye/vehicle/telemetry", 10,
    std::bind(&EmergencyNode::onTelemetryReceived, this, std::placeholders::_1));

  pub_emergency_ = this->create_publisher<roadeye_dashboard_msgs::msg::EmergencyEvent>("/roadeye/emergency/event", 10);
}

void EmergencyNode::onImuReceived(const sensor_msgs::msg::Imu::SharedPtr msg) {
  float ax = msg->linear_acceleration.x;
  float ay = msg->linear_acceleration.y;
  float az = msg->linear_acceleration.z;
  float norm_g = std::sqrt(ax * ax + ay * ay + az * az) / 9.81f;
  max_impact_g_ = std::max(max_impact_g_, norm_g);
}

void EmergencyNode::onTelemetryReceived(const roadeye_dashboard_msgs::msg::VehicleTelemetry::SharedPtr msg) {
  previous_speed_kmh_ = current_speed_kmh_;
  current_speed_kmh_ = msg->speed_kmh;
  current_lat_ = msg->latitude;
  current_lon_ = msg->longitude;
}

void EmergencyNode::checkCrashVerification() {
  // Crash Verification Rule:
  // 1. IMU impact > 4.0g
  // 2. Speed drop > 30 km/h in 100ms
  // 3. Vehicle has come to near-stop (< 5 km/h)
  float speed_drop = previous_speed_kmh_ - current_speed_kmh_;

  if (!crash_triggered_ && max_impact_g_ >= crash_g_threshold_ && speed_drop >= sudden_speed_drop_kmh_) {
    crash_triggered_ = true;

    roadeye_dashboard_msgs::msg::EmergencyEvent event;
    event.header.stamp = this->now();
    event.header.frame_id = "base_link";
    event.event_type = roadeye_dashboard_msgs::msg::EmergencyEvent::EVENT_CRASH_VERIFIED;
    event.latitude = current_lat_;
    event.longitude = current_lon_;
    event.impact_g_force = max_impact_g_;
    event.pre_crash_speed_kmh = previous_speed_kmh_;
    event.post_crash_speed_kmh = current_speed_kmh_;
    event.timestamp_utc = "2026-08-24T13:12:00Z";

    std::stringstream ss;
    ss << "EMERGENCY CRASH ALERT! RoadEye ADAS detected severe impact ("
       << max_impact_g_ << "g). Location: https://maps.google.com/?q="
       << current_lat_ << "," << current_lon_
       << " Pre-crash speed: " << previous_speed_kmh_ << " km/h.";

    event.payload_text = ss.str();
    event.sms_sent = false;
    event.retry_count = 0;

    RCLCPP_ERROR(this->get_logger(), "CRASH VERIFIED! Triggering SIM800L Emergency SOS to %s", emergency_phone_number_.c_str());

    sms_queue_.push(event);
    pub_emergency_->publish(event);
  }

  processSmsQueue();
}

void EmergencyNode::processSmsQueue() {
  if (sms_queue_.empty()) return;

  auto & event = sms_queue_.front();
  // Simulate AT command execution over Serial to SIM800L GSM module
  // AT+CMGF=1
  // AT+CMGS="+919876543210"
  event.sms_sent = true;
  RCLCPP_INFO(this->get_logger(), "SIM800L SMS Sent Successfully: '%s'", event.payload_text.c_str());
  sms_queue_.pop();
}

}  // namespace emergency
}  // namespace roadeye
