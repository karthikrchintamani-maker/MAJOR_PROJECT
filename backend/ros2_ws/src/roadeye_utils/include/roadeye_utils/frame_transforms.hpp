#ifndef ROADEYE_UTILS__FRAME_TRANSFORMS_HPP_
#define ROADEYE_UTILS__FRAME_TRANSFORMS_HPP_

#include <geometry_msgs/msg/point.hpp>
#include <geometry_msgs/msg/transform_stamped.hpp>
#include <tf2/LinearMath/Transform.h>

namespace roadeye {
namespace utils {

class FrameTransforms {
public:
  // Transform 3D camera coordinate (X_cam: right, Y_cam: down, Z_cam: forward) to vehicle base_link frame (X: forward, Y: left, Z: up)
  static geometry_msgs::msg::Point cameraToBaseLink(
    float cam_x, float cam_y, float cam_z,
    float camera_height_m = 1.2f, float camera_pitch_rad = 0.0f);

  // Compute 2D pixel to 3D camera ray projection given camera intrinsic matrix K
  static void pixelToCameraRay(
    float u, float v, float fx, float fy, float cx, float cy,
    float & ray_x, float & ray_y, float & ray_z);
};

}  // namespace utils
}  // namespace roadeye

#endif  // ROADEYE_UTILS__FRAME_TRANSFORMS_HPP_
