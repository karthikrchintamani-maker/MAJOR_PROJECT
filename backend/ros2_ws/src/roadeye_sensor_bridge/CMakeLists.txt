cmake_minimum_required(VERSION 3.8)
project(roadeye_sensor_bridge)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(roadeye_dashboard_msgs REQUIRED)
find_package(roadeye_utils REQUIRED)

include_directories(include)

add_executable(sensor_bridge_node
  src/sensor_bridge_node.cpp
  src/main.cpp
)

target_include_directories(sensor_bridge_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(sensor_bridge_node
  rclcpp
  sensor_msgs
  geometry_msgs
  roadeye_dashboard_msgs
  roadeye_utils
)

install(TARGETS sensor_bridge_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

ament_package()
