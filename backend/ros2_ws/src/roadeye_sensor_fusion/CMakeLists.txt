cmake_minimum_required(VERSION 3.8)
project(roadeye_sensor_fusion)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(roadeye_dashboard_msgs REQUIRED)
find_package(roadeye_utils REQUIRED)

include_directories(include)

add_executable(fusion_node
  src/fusion_node.cpp
  src/main.cpp
)

target_include_directories(fusion_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(fusion_node
  rclcpp
  std_msgs
  sensor_msgs
  geometry_msgs
  roadeye_dashboard_msgs
  roadeye_utils
)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_fusion test/test_fusion.cpp)
  target_include_directories(test_fusion PUBLIC include)
  ament_target_dependencies(test_fusion rclcpp sensor_msgs roadeye_dashboard_msgs roadeye_utils)
endif()

install(TARGETS fusion_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

ament_package()
