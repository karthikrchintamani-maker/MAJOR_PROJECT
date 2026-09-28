cmake_minimum_required(VERSION 3.8)
project(roadeye_perception)

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
find_package(cv_bridge REQUIRED)
find_package(image_transport REQUIRED)
find_package(OpenCV REQUIRED)

find_package(roadeye_dashboard_msgs REQUIRED)
find_package(roadeye_utils REQUIRED)

include_directories(include ${OpenCV_INCLUDE_DIRS})

add_executable(perception_node
  src/onnx_engine.cpp
  src/perception_node.cpp
  src/main.cpp
)

target_include_directories(perception_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

target_link_libraries(perception_node ${OpenCV_LIBS})

ament_target_dependencies(perception_node
  rclcpp
  sensor_msgs
  geometry_msgs
  cv_bridge
  image_transport
  roadeye_dashboard_msgs
  roadeye_utils
)

install(TARGETS perception_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

ament_package()
