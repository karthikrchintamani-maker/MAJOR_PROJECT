#include "roadeye_perception/perception_node.hpp"
#include <cv_bridge/cv_bridge.h>

namespace roadeye {
namespace perception {

PerceptionNode::PerceptionNode(const rclcpp::NodeOptions & options)
: Node("roadeye_perception_node", options),
  engine_(std::make_unique<OnnxInferenceEngine>())
{
  initParameters();
  initSubscribersAndPublishers();

  engine_->loadModels(
    model_det_path_, model_seg_path_, model_pothole_path_, model_depth_path_);

  if (use_sim_camera_) {
    sim_timer_ = this->create_wall_timer(
      std::chrono::milliseconds(66), // ~15 FPS
      std::bind(&PerceptionNode::processSyntheticFrame, this));
  }

  RCLCPP_INFO(this->get_logger(), "RoadEye C++ Perception Node started successfully.");
}

void PerceptionNode::initParameters() {
  this->declare_parameter("model_det_path", "models/detection/yolo26n_indian_road_best.onnx");
  this->declare_parameter("model_seg_path", "models/segmentation/yolo11m-road-seg.onnx");
  this->declare_parameter("model_pothole_path", "models/pothole/pothole-detection-yolov8.onnx");
  this->declare_parameter("model_depth_path", "models/depth/unet_depthwise_nano_best.onnx");
  this->declare_parameter("conf_threshold", 0.4f);
  this->declare_parameter("use_sim_camera", true);

  model_det_path_ = this->get_parameter("model_det_path").as_string();
  model_seg_path_ = this->get_parameter("model_seg_path").as_string();
  model_pothole_path_ = this->get_parameter("model_pothole_path").as_string();
  model_depth_path_ = this->get_parameter("model_depth_path").as_string();
  conf_threshold_ = static_cast<float>(this->get_parameter("conf_threshold").as_double());
  use_sim_camera_ = this->get_parameter("use_sim_camera").as_bool();
}

void PerceptionNode::initSubscribersAndPublishers() {
  sub_camera_ = this->create_subscription<sensor_msgs::msg::Image>(
    "/image_raw", 10, std::bind(&PerceptionNode::onImageReceived, this, std::placeholders::_1));

  pub_objects_ = this->create_publisher<roadeye_dashboard_msgs::msg::ObjectDetectionArray>(
    "/roadeye/perception/objects", 10);
  pub_potholes_ = this->create_publisher<roadeye_dashboard_msgs::msg::PotholeArray>(
    "/roadeye/perception/potholes", 10);
  pub_lane_state_ = this->create_publisher<roadeye_dashboard_msgs::msg::LaneState>(
    "/roadeye/perception/lane_state", 10);
  pub_driver_state_ = this->create_publisher<roadeye_dashboard_msgs::msg::DriverState>(
    "/roadeye/perception/driver_state", 10);
}

void PerceptionNode::initImageTransport() {
  if (pub_image_initialized_) return;
  image_transport::ImageTransport it(shared_from_this());
  pub_annotated_image_ = it.advertise("/roadeye/perception/annotated_image", 1);
  pub_image_initialized_ = true;
}

void PerceptionNode::onImageReceived(const sensor_msgs::msg::Image::ConstSharedPtr & msg) {
  initImageTransport();
  try {
    cv_bridge::CvImagePtr cv_ptr = cv_bridge::toCvCopy(msg, sensor_msgs::image_encodings::BGR8);
    cv::Mat frame = cv_ptr->image;

    auto objects = engine_->processObjectDetection(frame, conf_threshold_);
    auto potholes = engine_->processPotholeDetection(frame);
    auto lane_state = engine_->processLaneSegmentation(frame);

    objects.header = msg->header;
    potholes.header = msg->header;
    lane_state.header = msg->header;

    pub_objects_->publish(objects);
    pub_potholes_->publish(potholes);
    pub_lane_state_->publish(lane_state);

  } catch (const cv_bridge::Exception & e) {
    RCLCPP_ERROR(this->get_logger(), "cv_bridge exception: %s", e.what());
  }
}

void PerceptionNode::processSyntheticFrame() {
  initImageTransport();
  cv::Mat frame(480, 640, CV_8UC3, cv::Scalar(40, 40, 40));

  // Draw simulated road lines
  cv::line(frame, cv::Point(100, 480), cv::Point(280, 240), cv::Scalar(255, 255, 255), 3);
  cv::line(frame, cv::Point(540, 480), cv::Point(360, 240), cv::Scalar(255, 255, 255), 3);

  auto now = this->now();
  std_msgs::msg::Header header;
  header.stamp = now;
  header.frame_id = "camera_link";

  auto objects = engine_->processObjectDetection(frame, conf_threshold_);
  auto potholes = engine_->processPotholeDetection(frame);
  auto lane_state = engine_->processLaneSegmentation(frame);

  objects.header = header;
  potholes.header = header;
  lane_state.header = header;

  // Driver monitoring state
  roadeye_dashboard_msgs::msg::DriverState driver;
  driver.header = header;
  driver.face_detected = true;
  driver.eye_closure_ratio = 0.15f;
  driver.attentiveness_score = 0.95f;
  driver.is_drowsy = false;
  driver.is_distracted = false;

  pub_objects_->publish(objects);
  pub_potholes_->publish(potholes);
  pub_lane_state_->publish(lane_state);
  pub_driver_state_->publish(driver);
}

}  // namespace perception
}  // namespace roadeye
