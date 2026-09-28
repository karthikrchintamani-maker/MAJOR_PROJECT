cmake_minimum_required(VERSION 3.8)
project(roadeye_vehicle_interface)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(roadeye_dashboard_msgs REQUIRED)

include_directories(include)

add_executable(vehicle_interface_node
  src/vehicle_interface_node.cpp
  src/main.cpp
)

target_include_directories(vehicle_interface_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(vehicle_interface_node
  rclcpp
  geometry_msgs
  nav_msgs
  tf2
  tf2_ros
  roadeye_dashboard_msgs
)

install(TARGETS vehicle_interface_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

ament_package()
