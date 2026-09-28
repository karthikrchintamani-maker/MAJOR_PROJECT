#include <rclcpp/rclcpp.hpp>
#include "roadeye_vehicle_interface/vehicle_interface_node.hpp"

int main(int argc, char ** argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<roadeye::vehicle::VehicleInterfaceNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
