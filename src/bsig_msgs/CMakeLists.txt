cmake_minimum_required(VERSION 3.8)
project(bsig_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Prediction.msg"
  "msg/InferenceResult.msg"
  "msg/StreamResult.msg"
  "msg/Affect.msg"
  DEPENDENCIES builtin_interfaces std_msgs
)

ament_package()
