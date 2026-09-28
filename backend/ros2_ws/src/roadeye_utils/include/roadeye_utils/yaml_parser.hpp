#ifndef ROADEYE_UTILS__YAML_PARSER_HPP_
#define ROADEYE_UTILS__YAML_PARSER_HPP_

#include <string>
#include <vector>
#include <map>
#include <yaml-cpp/yaml.h>

namespace roadeye {
namespace utils {

class YamlParser {
public:
  explicit YamlParser(const std::string & file_path);
  ~YamlParser() = default;

  bool isLoaded() const;

  template<typename T>
  T get(const std::string & key, const T & default_value) const {
    if (!loaded_) {
      return default_value;
    }
    try {
      if (node_[key]) {
        return node_[key].as<T>();
      }
    } catch (...) {
      // Fall back to default value
    }
    return default_value;
  }

  YAML::Node getNode() const { return node_; }

private:
  YAML::Node node_;
  bool loaded_{false};
};

}  // namespace utils
}  // namespace roadeye

#endif  // ROADEYE_UTILS__YAML_PARSER_HPP_
