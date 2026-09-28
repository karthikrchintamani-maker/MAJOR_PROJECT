#include "roadeye_utils/yaml_parser.hpp"
#include <iostream>

namespace roadeye {
namespace utils {

YamlParser::YamlParser(const std::string & file_path) {
  try {
    node_ = YAML::LoadFile(file_path);
    loaded_ = true;
  } catch (const std::exception & e) {
    std::cerr << "[YamlParser] Error loading YAML file " << file_path << ": " << e.what() << std::endl;
    loaded_ = false;
  }
}

bool YamlParser::isLoaded() const {
  return loaded_;
}

}  // namespace utils
}  // namespace roadeye
