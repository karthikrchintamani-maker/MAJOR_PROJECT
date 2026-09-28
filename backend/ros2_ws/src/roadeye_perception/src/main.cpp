#include <rclcpp/rclcpp.hpp>
#include "roadeye_perception/perception_node.hpp"

int main(int argc, char ** argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<roadeye::perception::PerceptionNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
