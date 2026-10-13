# Builds the workspace and runs the tests. Versions come from Ubuntu 24.04 and ROS 2 Jazzy:
# python3-grpcio 1.51.1, python3-protobuf 3.21.12, ros-jazzy-audio-common-msgs 0.4.1.
FROM ros:jazzy

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3-grpcio python3-protobuf python3-pytest ros-jazzy-audio-common-msgs \
    && rm -rf /var/lib/apt/lists/*

# Keeps the tests off the host's DDS network (a host microphone would leak into them).
ENV ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST

WORKDIR /ws
COPY src src
RUN . /opt/ros/jazzy/setup.sh && colcon build

CMD ["bash", "-c", ". /opt/ros/jazzy/setup.sh && . install/setup.sh && python3 -m pytest -q src/bsig_ros/test"]
