#include "roadeye_utils/math_utils.hpp"
#include <limits>

namespace roadeye {
namespace utils {

float MathUtils::calculateTTC(float relative_distance_m, float relative_velocity_ms) {
  // relative_velocity_ms > 0 means approaching (closing speed)
  if (relative_velocity_ms <= 0.001f || relative_distance_m <= 0.0f) {
    return std::numeric_limits<float>::max();
  }
  return relative_distance_m / relative_velocity_ms;
}

double MathUtils::haversineDistanceMeters(double lat1, double lon1, double lat2, double lon2) {
  constexpr double R = 6371000.0; // Earth radius in meters
  double dLat = degToRad(lat2 - lat1);
  double dLon = degToRad(lon2 - lon1);
  double a = std::sin(dLat / 2.0) * std::sin(dLat / 2.0) +
             std::cos(degToRad(lat1)) * std::cos(degToRad(lat2)) *
             std::sin(dLon / 2.0) * std::sin(dLon / 2.0);
  double c = 2.0 * std::atan2(std::sqrt(a), std::sqrt(1.0 - a));
  return R * c;
}

float MathUtils::calculateRiskScore(float ttc_sec, float distance_m, float speed_kmh, float lane_offset_m) {
  float score = 0.0f;

  // TTC contribution (up to 50 pts)
  if (ttc_sec < 1.5f) {
    score += 50.0f;
  } else if (ttc_sec < 3.0f) {
    score += 50.0f * (3.0f - ttc_sec) / 1.5f;
  }

  // Distance contribution (up to 25 pts)
  if (distance_m < 5.0f) {
    score += 25.0f;
  } else if (distance_m < 15.0f) {
    score += 25.0f * (15.0f - distance_m) / 10.0f;
  }

  // Lane offset contribution (up to 15 pts)
  float abs_offset = std::abs(lane_offset_m);
  if (abs_offset > 0.6f) {
    score += std::min(15.0f, (abs_offset - 0.6f) * 20.0f);
  }

  // Speed factor multiplier
  if (speed_kmh > 80.0f) {
    score *= 1.2f;
  }

  return clamp(score, 0.0f, 100.0f);
}

}  // namespace utils
}  // namespace roadeye
