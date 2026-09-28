#include <gtest/gtest.h>

TEST(EmergencyLogicTest, CrashVerificationCriteria) {
  float g_force = 4.8f;
  float speed_drop = 35.0f;
  float crash_g_thresh = 4.0f;
  float speed_drop_thresh = 30.0f;

  bool is_crash = (g_force >= crash_g_thresh && speed_drop >= speed_drop_thresh);
  EXPECT_TRUE(is_crash);
}

int main(int argc, char ** argv) {
  testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
