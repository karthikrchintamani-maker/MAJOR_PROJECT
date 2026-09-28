#ifndef ROADEYE_PERCEPTION__PERCEPTION_NODE_HPP_
#define ROADEYE_PERCEPTION__PERCEPTION_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <cv_bridge/cv_bridge.h>
#include <image_transport/image_transport.hpp>

#include <roadeye_dashboard_msgs/msg/object_detection_array.hpp>
#include <roadeye_dashboard_msgs/msg/pothole_array.hpp>
#include <roadeye_dashboard_msgs/msg/lane_state.hpp>
#include <roadeye_dashboard_msgs/msg/driver_state.hpp>

#include "roadeye_perception/onnx_engine.hpp"

namespace roadeye {
namespace perception {

class PerceptionNode : public rclcpp::Node {
public:
  explicit PerceptionNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());
  ~PerceptionNode() override = default;

private:
  void initParameters();
  void initSubscribersAndPublishers();
  void initImageTransport();
  void onImageReceived(const sensor_msgs::msg::Image::ConstSharedPtr & msg);
  void processSyntheticFrame();

  std::string model_det_path_;
  std::string model_seg_path_;
  std::string model_pothole_path_;
  std::string model_depth_path_;
  float conf_threshold_{0.4f};
  bool use_sim_camera_{true};

  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr sub_camera_;
  rclcpp::Publisher<roadeye_dashboard_msgs::msg::ObjectDetectionArray>::SharedPtr pub_objects_;
  rclcpp::Publisher<roadeye_dashboard_msgs::msg::PotholeArray>::SharedPtr pub_potholes_;
  rclcpp::Publisher<roadeye_dashboard_msgs::msg::LaneState>::SharedPtr pub_lane_state_;
  rclcpp::Publisher<roadeye_dashboard_msgs::msg::DriverState>::SharedPtr pub_driver_state_;

  image_transport::Publisher pub_annotated_image_;
  bool pub_image_initialized_{false};
  rclcpp::TimerBase::SharedPtr sim_timer_;

  std::unique_ptr<OnnxInferenceEngine> engine_;
};

}  // namespace perception
}  // namespace roadeye

#endif  // ROADEYE_PERCEPTION__PERCEPTION_NODE_HPP_
