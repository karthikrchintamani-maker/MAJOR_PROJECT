cmake_minimum_required(VERSION 3.8)
project(roadeye_emergency)

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
find_package(roadeye_dashboard_msgs REQUIRED)
find_package(roadeye_utils REQUIRED)

include_directories(include)

add_executable(emergency_node
  src/emergency_node.cpp
  src/main.cpp
)

target_include_directories(emergency_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(emergency_node
  rclcpp
  std_msgs
  sensor_msgs
  roadeye_dashboard_msgs
  roadeye_utils
)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_emergency test/test_emergency.cpp)
  target_include_directories(test_emergency PUBLIC include)
  ament_target_dependencies(test_emergency rclcpp std_msgs roadeye_dashboard_msgs roadeye_utils)
endif()

install(TARGETS emergency_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

ament_package()
