#include <rclcpp/rclcpp.hpp>
#include "roadeye_sensor_bridge/sensor_bridge_node.hpp"

int main(int argc, char ** argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<roadeye::bridge::SensorBridgeNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
