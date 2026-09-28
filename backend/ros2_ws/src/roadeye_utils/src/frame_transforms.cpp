#include "roadeye_utils/frame_transforms.hpp"
#include <cmath>

namespace roadeye {
namespace utils {

geometry_msgs::msg::Point FrameTransforms::cameraToBaseLink(
  float cam_x, float cam_y, float cam_z,
  float camera_height_m, float camera_pitch_rad)
{
  geometry_msgs::msg::Point pt;
  // Standard OpenCV camera frame: X_cam = right, Y_cam = down, Z_cam = forward
  // Base link frame: X_base = forward, Y_base = left, Z_base = up
  
  // Apply pitch rotation around Y_cam axis if any
  float z_rot = cam_z * std::cos(camera_pitch_rad) - cam_y * std::sin(camera_pitch_rad);
  float y_rot = cam_z * std::sin(camera_pitch_rad) + cam_y * std::cos(camera_pitch_rad);

  pt.x = z_rot;                  // Forward distance
  pt.y = -cam_x;                 // Left distance (negated right)
  pt.z = camera_height_m - y_rot; // Upward height from ground
  return pt;
}

void FrameTransforms::pixelToCameraRay(
  float u, float v, float fx, float fy, float cx, float cy,
  float & ray_x, float & ray_y, float & ray_z)
{
  ray_x = (u - cx) / fx;
  ray_y = (v - cy) / fy;
  ray_z = 1.0f;
}

}  // namespace utils
}  // namespace roadeye
