# AGENTS.md

ROS 2 integration for the [Behavioral Signals API](https://behavioralsignals.readme.io/): audio from a
ROS topic goes in, emotion, behavior, speaker and deepfake results come out as ROS topics. Usage, parameters
and topics are in [README.md](README.md). Test and pull request steps are in [CONTRIBUTING.md](CONTRIBUTING.md).

## Set up for a user

1. Check the system: Ubuntu 24.04 and ROS 2 Jazzy. Humble is not supported.
2. Install the dependencies. The list is in [docs/replay.md](docs/replay.md) (Requirements).
3. Ask the user to register at the [portal](https://portal.behavioralsignals.com/) and export
   `BEHAVIORALSIGNALS_CID` and `BEHAVIORALSIGNALS_API_KEY`. Never ask them to paste the key into the chat or a file.
4. From the repository root: `source /opt/ros/jazzy/setup.bash && colcon build && source install/setup.bash`.
5. Start the user's audio publisher, then `ros2 launch bsig_ros bsig.launch.py namespace:=mic1`.
   The audio must be mono S16LE; see "Audio" in the README.
6. To try it without a microphone, follow [docs/replay.md](docs/replay.md).

## Map

- `src/bsig_msgs/msg/`: the messages `Prediction`, `InferenceResult`, `StreamResult` and `Affect`.
- `src/bsig_ros/bsig_ros/bridge.py`: the `bsig_bridge` node (audio in, gRPC stream, results out, reconnects).
  `session.py`: one stream. `chunker.py`: audio chunks. `mapping.py`: API responses to ROS messages.
  `convert.py`: time, chunk size and audio format helpers. `diagnostics.py`: the diagnostics status.
- `src/bsig_ros/bsig_ros/affect.py`, `smoothing.py`: the `bsig_affect` node (valence and arousal).
- `src/bsig_ros/bsig_ros/api_pb2*.py`: generated from `src/bsig_ros/protos/api.proto`.
- `src/bsig_ros/launch/`, `src/bsig_ros/config/`: launch file and default parameters.
- `tools/`: replay, CSV export and summary scripts. `src/bsig_ros/test/`: pytest tests.

## Commands

```bash
docker build -t behavioralsignals-ros2 -f docker/Dockerfile .
docker run --rm behavioralsignals-ros2   # builds the workspace and runs all tests
```

CI runs the same two commands.

## Rules

- Tests never call the API and need no credentials. Use `test/fake_api.py`.
- Don't edit `api_pb2*.py` by hand; run `src/bsig_ros/protos/generate.sh`.
- When you add or change a parameter, update the README parameter table and `config/bsig.yaml` if it belongs there.
- When you change a message, update the README results section.
- Keep the node names, topic names and package names `bsig_ros` and `bsig_msgs`. Users depend on them.
- Never commit credentials.
