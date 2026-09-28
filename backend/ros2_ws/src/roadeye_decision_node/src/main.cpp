#include <rclcpp/rclcpp.hpp>
#include "roadeye_decision_node/decision_node.hpp"

int main(int argc, char ** argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<roadeye::decision::DecisionNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
