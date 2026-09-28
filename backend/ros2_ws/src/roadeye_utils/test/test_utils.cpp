#include <gtest/gtest.h>
#include "roadeye_utils/math_utils.hpp"
#include "roadeye_utils/frame_transforms.hpp"

using namespace roadeye::utils;

TEST(MathUtilsTest, CalculateTTC) {
  float ttc = MathUtils::calculateTTC(20.0f, 10.0f); // 20m at 10 m/s closing speed -> 2.0s
  EXPECT_NEAR(ttc, 2.0f, 1e-4f);

  float ttc_receding = MathUtils::calculateTTC(20.0f, -5.0f); // receding
  EXPECT_GT(ttc_receding, 1000.0f);
}

TEST(MathUtilsTest, HaversineDistance) {
  // New Delhi (28.6139, 77.2090) to Mumbai (19.0760, 72.8777) ~1150 km
  double dist = MathUtils::haversineDistanceMeters(28.6139, 77.2090, 19.0760, 72.8777);
  EXPECT_NEAR(dist, 1148000.0, 20000.0);
}

TEST(MathUtilsTest, RiskScore) {
  float risk = MathUtils::calculateRiskScore(1.0f, 4.0f, 90.0f, 0.8f);
  EXPECT_GT(risk, 70.0f);
}

TEST(FrameTransformsTest, CameraToBaseLink) {
  auto pt = FrameTransforms::cameraToBaseLink(0.5f, 0.0f, 10.0f, 1.2f, 0.0f);
  EXPECT_NEAR(pt.x, 10.0f, 1e-3f);
  EXPECT_NEAR(pt.y, -0.5f, 1e-3f);
  EXPECT_NEAR(pt.z, 1.2f, 1e-3f);
}

int main(int argc, char ** argv) {
  testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
