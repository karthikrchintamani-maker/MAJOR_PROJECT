#ifndef ROADEYE_PERCEPTION__ONNX_ENGINE_HPP_
#define ROADEYE_PERCEPTION__ONNX_ENGINE_HPP_

#include <string>
#include <vector>
#include <memory>
#include <opencv2/opencv.hpp>
#include <roadeye_dashboard_msgs/msg/object_detection_array.hpp>
#include <roadeye_dashboard_msgs/msg/pothole_array.hpp>
#include <roadeye_dashboard_msgs/msg/lane_state.hpp>

namespace roadeye {
namespace perception {

struct DetectionBox {
  int class_id;
  std::string label;
  float confidence;
  cv::Rect2f bbox;
};

class OnnxInferenceEngine {
public:
  OnnxInferenceEngine();
  ~OnnxInferenceEngine();

  bool loadModels(
    const std::string & det_path,
    const std::string & seg_path,
    const std::string & pothole_path,
    const std::string & depth_path);

  roadeye_dashboard_msgs::msg::ObjectDetectionArray processObjectDetection(
    const cv::Mat & frame, float conf_threshold = 0.4f);

  roadeye_dashboard_msgs::msg::PotholeArray processPotholeDetection(
    const cv::Mat & frame, float conf_threshold = 0.35f);

  roadeye_dashboard_msgs::msg::LaneState processLaneSegmentation(
    const cv::Mat & frame);

  cv::Mat estimateDepth(const cv::Mat & frame);

private:
  bool models_loaded_{false};
  std::vector<std::string> class_names_{
    "car", "truck", "bus", "motorcycle", "auto_rickshaw", "pedestrian", "bicycle", "animal", "traffic_sign"
  };
};

}  // namespace perception
}  // namespace roadeye

#endif  // ROADEYE_PERCEPTION__ONNX_ENGINE_HPP_
