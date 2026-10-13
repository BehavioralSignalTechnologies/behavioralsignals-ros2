# Replay a recording through the API

This plays an audio recording into the ROS 2 nodes, sends it to the Behavioral Signals API and saves the
results as a rosbag.

## Requirements

- Ubuntu 24.04 with ROS 2 Jazzy.
- `sudo apt install ros-jazzy-ros-base ros-jazzy-audio-common-msgs ros-jazzy-rosbag2-storage-mcap python3-grpcio python3-protobuf python3-colcon-common-extensions ffmpeg`
- API credentials. Register in the [Behavioral Signals portal](https://portal.behavioralsignals.com/) to get a CID and an API key.
  Put them in the environment (they are never written to files):

```
export BEHAVIORALSIGNALS_CID=<your cid>
export BEHAVIORALSIGNALS_API_KEY=<your key>
```

## Steps

Run these in bash, from the repository root.

1. Build the workspace.

```
source /opt/ros/jazzy/setup.bash
colcon build
source install/setup.bash
```

2. Convert the recording to 16 kHz mono 16-bit WAV, then to a rosbag.

```
ffmpeg -i recording.mov -vn -ac 1 -ar 16000 -c:a pcm_s16le recording.wav
python3 tools/wav_to_bag.py recording.wav recording_audio
```

3. Replay it. The script starts the behavior bridge, the deepfake bridge and the affect node. It records `/bsig/results`,
`/bsig/affect`, `/bsig/deepfake` and `/diagnostics`, and plays the bag in real time. The last argument is the run time in seconds: the length of
the recording plus about 15 s.

```
tools/replay.sh recording_audio recording_results 80
```

4. Print the timeline.

```
python3 tools/summarize_results.py recording_results
```

5. Write plain CSV files of the same results.

```
python3 tools/results_to_csv.py recording_results recording
```

This writes `recording_api_results.csv` (every label the API returned, one per row), `recording_affect.csv`
and `recording_deepfake.csv`.

## Example output

The start of the printout for a 61 s recording (shortened):

```
Part 1: API results, 33 windows covering 0 to 61 s of audio
    window (s)  level      emotion             positivity          strength            gender
   2.0 -   4.0  segment    neutral (0.44)      neutral (0.50)      neutral (0.71)      female (1.00)
   2.0 -   4.0  utterance  neutral (0.44)      neutral (0.50)      neutral (0.71)      female (1.00)
   6.0 -   7.0  segment    angry (0.41)        neutral (0.52)      neutral (0.52)      female (1.00)
   6.0 -   7.0  utterance  angry (0.41)        neutral (0.52)      neutral (0.52)      female (1.00)
   9.0 -  11.0  segment    happy (0.87)        positive (0.79)     neutral (0.71)      female (1.00)
   9.0 -  16.0  utterance  happy (0.80)        positive (0.69)     neutral (0.69)      female (1.00)
   ...

Part 2: smoothed affect from bsig_affect, 27 messages
time (s)  emotion    valence   arousal  confidence
     4.0  neutral      -0.43     -0.22        0.44
     8.0  angry        -0.16     +0.22        0.41
    11.1  happy        +0.53     +0.22        0.87
    13.1  happy        +0.65     +0.09        0.82
    15.0  neutral      +0.34     +0.04        0.92
    17.1  happy        +0.48     +0.10        0.90
   ...
```

## What the output shows

The printout starts with a short "How to read this file" block. Then:

- Part 1 is what the API returned: one line per window of audio, with the level (`segment` or `utterance`)
  and the top label of `emotion`, `positivity`, `strength` and `gender`, each with its confidence.
  A confidence below about 0.7 is weak. Times are seconds from the start of the audio.
- Utterance results arrive after the phrase ends and cover earlier time, so the lines are sorted by start time.
- Part 2 is the smoothed `valence` and `arousal` from our `bsig_affect` node. It is not API output.
- Part 3 is what the API's deepfake detection returned: `bonafide` (real speech) or `spoofed` (fake speech),
  with its confidence.

## Play the saved bags again

`ros2 bag play --delay 3 recording_audio` publishes `/audio_info` and `/audio_stamped`. The delay lets DDS match
the publisher with the bridge; without it the first seconds of audio can be lost.
