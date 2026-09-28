cmake_minimum_required(VERSION 3.8)
project(roadeye_dashboard_msgs)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/WarningAlert.msg"
  "msg/SensorHealth.msg"
  "msg/EmergencyEvent.msg"
  "msg/VehicleTelemetry.msg"
  "msg/PotholeAlert.msg"
  "msg/PotholeArray.msg"
  "msg/DriverState.msg"
  "msg/LaneState.msg"
  "msg/ObjectDetection.msg"
  "msg/ObjectDetectionArray.msg"
  DEPENDENCIES std_msgs geometry_msgs builtin_interfaces
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
