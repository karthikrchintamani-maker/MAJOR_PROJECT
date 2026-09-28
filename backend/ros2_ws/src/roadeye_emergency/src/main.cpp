#include <rclcpp/rclcpp.hpp>
#include "roadeye_emergency/emergency_node.hpp"

int main(int argc, char ** argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<roadeye::emergency::EmergencyNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
