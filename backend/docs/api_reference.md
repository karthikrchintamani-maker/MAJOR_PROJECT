# RoadEye — C++ Class & Node API Reference

## C++ Core Classes

### `roadeye::utils::MathUtils`
- `static float calculateTTC(float relative_distance_m, float relative_velocity_ms)`: Returns Time-To-Collision in seconds.
- `static double haversineDistanceMeters(double lat1, double lon1, double lat2, double lon2)`: Returns spatial GPS distance in meters.
- `static float calculateRiskScore(float ttc_sec, float distance_m, float speed_kmh, float lane_offset_m)`: Computes composite risk score (0-100).

### `roadeye::perception::OnnxInferenceEngine`
- `bool loadModels(const std::string & det, const std::string & seg, const std::string & pothole, const std::string & depth)`
- `ObjectDetectionArray processObjectDetection(const cv::Mat & frame, float conf_thresh)`
- `PotholeArray processPotholeDetection(const cv::Mat & frame, float conf_thresh)`
- `LaneState processLaneSegmentation(const cv::Mat & frame)`
