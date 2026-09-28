#include <gtest/gtest.h>
#include "roadeye_utils/math_utils.hpp"

TEST(SensorFusionLogicTest, EKFDistanceWeighting) {
  float cam_dist = 10.0f;
  float lidar_dist = 9.0f;
  float weight_cam = 0.4f;
  float weight_lidar = 0.6f;

  float fused = weight_cam * cam_dist + weight_lidar * lidar_dist;
  EXPECT_NEAR(fused, 9.4f, 1e-4f);
}

int main(int argc, char ** argv) {
  testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
