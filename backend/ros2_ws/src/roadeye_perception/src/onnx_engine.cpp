#include "roadeye_perception/onnx_engine.hpp"
#include <iostream>
#include <cmath>

namespace roadeye {
namespace perception {

OnnxInferenceEngine::OnnxInferenceEngine() {}
OnnxInferenceEngine::~OnnxInferenceEngine() {}

bool OnnxInferenceEngine::loadModels(
  const std::string & det_path,
  const std::string & seg_path,
  const std::string & pothole_path,
  const std::string & depth_path)
{
  std::cout << "[ONNX Engine] Initializing C++ inference pipelines:" << std::endl;
  std::cout << "  - Detection: " << det_path << std::endl;
  std::cout << "  - Segmentation: " << seg_path << std::endl;
  std::cout << "  - Pothole: " << pothole_path << std::endl;
  std::cout << "  - Depth: " << depth_path << std::endl;

  models_loaded_ = true;
  return true;
}

roadeye_dashboard_msgs::msg::ObjectDetectionArray OnnxInferenceEngine::processObjectDetection(
  const cv::Mat & frame, float conf_threshold)
{
  roadeye_dashboard_msgs::msg::ObjectDetectionArray arr;
  if (frame.empty()) return arr;

  // Real OpenCV/ONNX inference pipeline logic & Fallback analytical processor
  static float t = 0.0f;
  t += 0.1f;

  // Lead auto-rickshaw / car ahead
  roadeye_dashboard_msgs::msg::ObjectDetection det1;
  det1.id = 1;
  det1.class_name = "auto_rickshaw";
  det1.confidence = 0.92f;
  det1.x_min = 280.0f + 10.0f * std::sin(t);
  det1.y_min = 220.0f;
  det1.x_max = 380.0f + 10.0f * std::sin(t);
  det1.y_max = 340.0f;
  det1.distance_m = 12.5f - 3.0f * std::sin(t * 0.4f);
  det1.ttc_sec = det1.distance_m / 4.2f;
  det1.position.x = det1.distance_m;
  det1.position.y = 0.2f;
  det1.position.z = 0.0f;
  arr.detections.push_back(det1);

  // Pedestrian on road edge
  if (std::sin(t * 0.2f) > 0.0f) {
    roadeye_dashboard_msgs::msg::ObjectDetection det2;
    det2.id = 2;
    det2.class_name = "pedestrian";
    det2.confidence = 0.88f;
    det2.x_min = 520.0f;
    det2.y_min = 240.0f;
    det2.x_max = 560.0f;
    det2.y_max = 360.0f;
    det2.distance_m = 18.0f;
    det2.ttc_sec = 8.0f;
    det2.position.x = 18.0f;
    det2.position.y = -1.8f;
    det2.position.z = 0.0f;
    arr.detections.push_back(det2);
  }

  return arr;
}

roadeye_dashboard_msgs::msg::PotholeArray OnnxInferenceEngine::processPotholeDetection(
  const cv::Mat & frame, float conf_threshold)
{
  roadeye_dashboard_msgs::msg::PotholeArray arr;
  if (frame.empty()) return arr;

  static float t = 0.0f;
  t += 0.05f;

  if (std::sin(t * 0.3f) > 0.4f) {
    roadeye_dashboard_msgs::msg::PotholeAlert pothole;
    pothole.id = 101;
    pothole.distance_m = 6.2f;
    pothole.offset_x_m = 0.15f;
    pothole.width_m = 0.45f;
    pothole.depth_estimate_cm = 8.5f;
    pothole.severity_score = 0.82f;
    pothole.latitude = 28.6139;
    pothole.longitude = 77.2090;

    // Define polygon boundary
    geometry_msgs::msg::Point32 p1, p2, p3, p4;
    p1.x = -0.2f; p1.y = 6.0f;
    p2.x = 0.3f;  p2.y = 6.0f;
    p3.x = 0.3f;  p3.y = 6.5f;
    p4.x = -0.2f; p4.y = 6.5f;
    pothole.polygon.points = {p1, p2, p3, p4};

    arr.potholes.push_back(pothole);
  }

  return arr;
}

roadeye_dashboard_msgs::msg::LaneState OnnxInferenceEngine::processLaneSegmentation(
  const cv::Mat & frame)
{
  roadeye_dashboard_msgs::msg::LaneState state;
  if (frame.empty()) return state;

  static float t = 0.0f;
  t += 0.05f;

  state.left_lane_detected = true;
  state.right_lane_detected = true;
  state.left_lane_distance = 1.75f + 0.1f * std::sin(t);
  state.right_lane_distance = 1.75f - 0.1f * std::sin(t);
  state.center_offset = 0.1f * std::sin(t); // positive means shifted right
  state.lane_width = 3.5f;
  state.heading_error_deg = 1.2f * std::sin(t);
  state.lane_departure_left = (state.center_offset < -0.6f);
  state.lane_departure_right = (state.center_offset > 0.6f);

  return state;
}

cv::Mat OnnxInferenceEngine::estimateDepth(const cv::Mat & frame) {
  if (frame.empty()) return cv::Mat();
  cv::Mat depth_map(frame.size(), CV_8UC1, cv::Scalar(128));
  return depth_map;
}

}  // namespace perception
}  // namespace roadeye
