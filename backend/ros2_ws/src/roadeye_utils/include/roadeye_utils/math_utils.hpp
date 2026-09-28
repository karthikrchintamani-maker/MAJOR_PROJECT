#ifndef ROADEYE_UTILS__MATH_UTILS_HPP_
#define ROADEYE_UTILS__MATH_UTILS_HPP_

#include <cmath>
#include <vector>
#include <algorithm>

namespace roadeye {
namespace utils {

class MathUtils {
public:
  // Calculate Time-To-Collision (TTC) in seconds given relative distance (m) and relative velocity (m/s)
  static float calculateTTC(float relative_distance_m, float relative_velocity_ms);

  // Calculate Haversine distance between two GPS lat/lon points in meters
  static double haversineDistanceMeters(double lat1, double lon1, double lat2, double lon2);

  // Calculate Risk Score (0.0 to 100.0) based on speed, distance, TTC, and lane offset
  static float calculateRiskScore(float ttc_sec, float distance_m, float speed_kmh, float lane_offset_m);

  // Clamp helper
  template<typename T>
  static T clamp(T val, T min_val, T max_val) {
    return std::max(min_val, std::min(val, max_val));
  }

  // Deg to Rad / Rad to Deg
  static constexpr double degToRad(double deg) { return deg * M_PI / 180.0; }
  static constexpr double radToDeg(double rad) { return rad * 180.0 / M_PI; }
};

}  // namespace utils
}  // namespace roadeye

#endif  // ROADEYE_UTILS__MATH_UTILS_HPP_
