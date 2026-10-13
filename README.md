# behavioralsignals-ros2

[![CI](https://github.com/BehavioralSignalTechnologies/behavioralsignals-ros2/actions/workflows/ci.yml/badge.svg)](https://github.com/BehavioralSignalTechnologies/behavioralsignals-ros2/actions/workflows/ci.yml)
[![Release](https://badgen.net/github/release/BehavioralSignalTechnologies/behavioralsignals-ros2)](https://github.com/BehavioralSignalTechnologies/behavioralsignals-ros2/releases)
[![License](https://badgen.net/badge/license/Apache-2.0/blue)](LICENSE)
[![ROS 2 Jazzy](https://badgen.net/badge/ROS%202/Jazzy/22314e)](https://docs.ros.org/en/jazzy/)

ROS 2 integration for the [Behavioral Signals API](https://behavioralsignals.readme.io/). Audio from a
ROS topic goes in. Emotion, behavior, speaker and deepfake results come out as time-stamped ROS topics.
No transcript is sent or returned.

Works with ROS 2 Jazzy on Ubuntu 24.04. ROS 2 Humble is not supported yet (see [Limits](#limits)).

[API documentation](https://behavioralsignals.readme.io/) ·
[Python SDK](https://github.com/BehavioralSignalTechnologies/behavioralsignals-python) ·
[Replay a recording](docs/replay.md) ·
[Contributing](CONTRIBUTING.md)

## Try it without a microphone

You need an API key and a short audio recording. Follow [docs/replay.md](docs/replay.md). It plays the
recording into the nodes and prints a timeline of the results.

## Packages

- `bsig_msgs`: the messages `Prediction`, `InferenceResult`, `StreamResult` and `Affect`.
- `bsig_ros`: the nodes `bsig_bridge` (talks to the API) and `bsig_affect` (smooths the results), plus
  `launch/bsig.launch.py` and `config/bsig.yaml`.

## Data flow

```
audio_capture -> <ns>/audio_stamped  (AudioDataStamped)
              -> <ns>/audio_info     (AudioInfo, transient local)

bsig_behavior (StreamAudio)       -> <ns>/bsig/results  -> bsig_affect -> <ns>/bsig/affect
bsig_deepfake (DeepfakeDetection) -> <ns>/bsig/deepfake
```

Use one namespace (`<ns>`) per microphone. Run one bridge per method.

| Topic | Type | Published by |
|---|---|---|
| `<ns>/bsig/results` | `bsig_msgs/StreamResult` | `bsig_behavior` |
| `<ns>/bsig/deepfake` | `bsig_msgs/StreamResult` | `bsig_deepfake` |
| `<ns>/bsig/affect` | `bsig_msgs/Affect` | `bsig_affect` |
| `<ns>/diagnostics` | `diagnostic_msgs/DiagnosticArray` | both bridges |

The message definitions are in [src/bsig_msgs/msg](src/bsig_msgs/msg).

## Run

Build the workspace, then start your audio publisher and the launch file. The launch file does not start
`audio_capture`.

```
source /opt/ros/jazzy/setup.bash
colcon build
source install/setup.bash
export BEHAVIORALSIGNALS_CID=...
export BEHAVIORALSIGNALS_API_KEY=...
ros2 launch bsig_ros bsig.launch.py namespace:=mic1
```

For a microphone, install `audio_capture` (`sudo apt install ros-jazzy-audio-capture`) and start it in the same namespace.
Its default format is `mp3`, so set `format:=wave`:

```
ros2 run audio_capture audio_capture_node --ros-args -r __ns:=/mic1 -p format:=wave
```

The launch file starts three nodes: `bsig_behavior`, `bsig_deepfake` and `bsig_affect`. The two bridges
open one stream each on the same key.

Register in the [Behavioral Signals portal](https://portal.behavioralsignals.com/) to get a CID and an API key.
Credentials come from the environment only. The bridge fails at start if either one is missing.

The bridge sends your audio to `endpoint`. Keep `use_tls` on unless the endpoint is on your own network.

To play a recorded file instead of a microphone, see [docs/replay.md](docs/replay.md).

## Audio

`audio_stamped` must carry mono, signed 16-bit little-endian PCM. `audio_capture` must run with `format: wave`.

At start, the bridge waits up to 2 s for `audio_info`. It checks `channels=1`, `sample_format=S16LE` and
`coding_format=wave`, and takes the sample rate from it.

- If the format is wrong, the bridge logs an error and sends no audio.
- If no `audio_info` arrives, the bridge uses the `sample_rate` parameter and logs a warning.
- If the sample rate changes, the stream restarts.

The bridge subscribes with reliable QoS and depth 100. If your audio publisher is best effort, set
`audio_qos_reliability: best_effort`. A gap in the audio shifts every later timestamp.

## Parameters (`bsig_bridge`)

| Name | Default | Meaning |
|---|---|---|
| `endpoint` | `streaming.behavioralsignals.com:443` | gRPC endpoint: cloud or on-premises/edge |
| `use_tls` | `true` | TLS on the channel |
| `method` | `StreamAudio` | `StreamAudio` or `DeepfakeDetection` |
| `level` | `all` | `all`, `segment` or `utterance` |
| `logits` | `false` | Ask the API for logits. They fill `Prediction.logit` |
| `sample_rate` | `16000` | Used only when no `audio_info` arrives |
| `chunk_ms` | `250` | Audio chunk size sent to the API, 100 to 500 |
| `idle_timeout_s` | `0` (off) | End the stream after this many seconds without audio. The next stream opens when audio returns. Set it to the server's idle timeout, or lower |
| `audio_qos_reliability` | `reliable` | `reliable` or `best_effort` |

`bsig_affect` has one parameter: `time_constant_s` (default `3.0`).

## Integration settings

Nothing here is hard-coded.

| Setting | How to set it |
|---|---|
| Audio topic | Run in a namespace, or remap `audio_stamped` and `audio_info` |
| Clock | Standard ROS time. For bag replay, use `use_sim_time:=true` and `ros2 bag play --clock` |
| Audio QoS | `audio_qos_reliability` |
| Endpoint and TLS | `endpoint`, `use_tls` |
| Sample rate | From `audio_info`, else `sample_rate` |
| Stream length | No maximum. The bridge restarts a stream whenever the server ends it |

The audio message type is `audio_common_msgs/AudioDataStamped`.

## Results

`bsig/results` carries `StreamResult` messages. `bsig/deepfake` carries the same type from the deepfake bridge.

- `header.stamp` is the time the result was received.
- `InferenceResult.start` and `end` are absolute ROS times. They are the header time of the first audio
  message of the stream, plus the API's relative times. Every reconnect starts a new stream and a new time origin.
- `level` is `segment` (2 s windows) or `utterance`. Utterance results arrive late and cover earlier time.
- `posterior` is NaN when the API does not return it. `logit` is NaN unless `logits` is true.
- A label with a low posterior is weak. Choose a `posterior` threshold for your use. 0.7 is a good start.

`bsig/affect` carries `Affect`, made by `bsig_affect` from segment results:

- valence = P(positive) − P(negative) of the API's `positivity` task, from −1 to +1.
- arousal = P(strong) − P(weak) of the API's `strength` task, from −1 to +1.
- Both are smoothed with an exponential moving average.
- It is published when a segment result arrives, once both values have been seen.

Thresholds are for the integrator to choose.

## Reconnect and drops

- **Stream ended with no error, or produced results:** the bridge reconnects at once.
- **Stream failed with no results:** the bridge waits 1 s, then doubles the wait on each repeat, up to 30 s.
- **Credentials rejected** (`PERMISSION_DENIED` or `UNAUTHENTICATED`): the bridge logs an error, stops
  connecting and reports `ERROR` in diagnostics until you restart it.

Audio that arrives while no stream is open is dropped and counted. If the 30 s queue fills, the bridge
restarts the stream, because a gap in the audio would shift every later result time.

The bridge logs a warning when no audio message arrives for 10 s, and when audio headers carry a zero stamp.

If the audio format is wrong at start, the bridge opens no stream. If `audio_info` turns bad later, the
audio stops and the running stream ends when the server closes it.

## Diagnostics

Each bridge publishes `diagnostic_msgs/DiagnosticArray` on `<ns>/diagnostics` once per second.

| Level | Message |
|---|---|
| `ERROR` | Unsupported audio format, with the reason |
| `ERROR` | `stopped, not retrying:` and the API error, for rejected credentials |
| `WARN` | `reconnecting after:` and the API error (for example `UNAVAILABLE: ...`) |
| `WARN` | `no audio`: no audio message in the last 10 s |
| `WARN` | `no stream open` |
| `OK` | `streaming` |

The values are counters since start:

- `streams_opened`: also counts a stream held back by `idle_timeout_s`. Divide by uptime to get reconnects per hour.
- `results`
- `dropped_idle`, `dropped_full`, `dropped_format`
- `unsent`
- `queue_high_water` (in chunks)

The other values are `stream_open` (true while the gRPC channel is connected), `audio_stalled`, `error`
and `fatal`.

## Limits

- Ubuntu 22.04 (ROS 2 Humble) is not supported. The stubs need protobuf 3.20 or newer.
- Result times are late by one buffer when the audio publisher stamps messages at publish time.
  `audio_capture` stamps at buffer start.

## Tests

```
docker build -t behavioralsignals-ros2 -f docker/Dockerfile .
docker run --rm behavioralsignals-ros2
```

- Unit tests cover chunking, sessions, conversion, mapping, smoothing and diagnostics.
- End-to-end tests run both nodes over real topics against a fake API in the same process. They cover
  absolute times, reconnect, the deepfake method, level, a bad audio format, missing credentials,
  diagnostics, queue overflow, a sample-rate change and QoS.
- The tests need no credentials and no network.
- The Docker image keeps DDS discovery on localhost, so a microphone on the host cannot reach the tests.

## Regenerating the API stubs

`src/bsig_ros/protos/api.proto` is the published proto. It is the same file as `protos/api.proto` in the
[Python SDK](https://github.com/BehavioralSignalTechnologies/behavioralsignals-python) v0.7.1 (last changed in
commit `f8d0b44`), copied on 2026-10-12. Its package is `behavioral_api.grpc.v1`.
`src/bsig_ros/protos/generate.sh` regenerates
`api_pb2*.py` with grpcio-tools 1.51.3. The result runs on protobuf 3.21 (Ubuntu 24.04 / ROS 2 Jazzy) and newer.

## Versions

ROS 2 Jazzy, Ubuntu 24.04, Python 3.12, `python3-grpcio` 1.51.1, `python3-protobuf` 3.21.12,
`ros-jazzy-audio-common-msgs` 0.4.1.

## Support

- Bugs and feature requests: [GitHub issues](https://github.com/BehavioralSignalTechnologies/behavioralsignals-ros2/issues).
  Never paste your API key or CID.
- Security problems: see [SECURITY.md](SECURITY.md).
- Anything else: api-support@behavioralsignals.com.
- Questions about the API: the [API documentation](https://behavioralsignals.readme.io/) and our
  [Discord](https://discord.com/invite/fxjRrbMH3Q).

## License

Apache License 2.0. See [LICENSE](LICENSE).
