#include <gtest/gtest.h>

TEST(DecisionRulesTest, AEBThresholdEvaluation) {
  float ttc = 0.9f;
  float aeb_threshold = 1.2f;

  bool trigger_aeb = (ttc > 0.0f && ttc <= aeb_threshold);
  EXPECT_TRUE(trigger_aeb);
}

TEST(DecisionRulesTest, FCWThresholdEvaluation) {
  float ttc = 2.1f;
  float fcw_threshold = 2.5f;

  bool trigger_fcw = (ttc > 0.0f && ttc <= fcw_threshold);
  EXPECT_TRUE(trigger_fcw);
}

int main(int argc, char ** argv) {
  testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
