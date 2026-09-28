#include <rclcpp/rclcpp.hpp>
#include "roadeye_sensor_fusion/fusion_node.hpp"

int main(int argc, char ** argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<roadeye::fusion::SensorFusionNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
