#!/usr/bin/env bash
# Plays an audio bag through the behavior bridge, the deepfake bridge and the affect node against the real API,
# and records the results.
# Usage: tools/replay.sh <audio_bag_dir> <results_bag_dir> [seconds]
# Needs BEHAVIORALSIGNALS_CID and BEHAVIORALSIGNALS_API_KEY in the environment, and a sourced workspace.
set -eu
audio_bag=$1
results_bag=$2
seconds=${3:-140}
: "${BEHAVIORALSIGNALS_CID:?}" "${BEHAVIORALSIGNALS_API_KEY:?}"

timeout -s INT "$seconds" ros2 run bsig_ros bsig_bridge --ros-args -r __node:=bsig_behavior -p logits:=true &
timeout -s INT "$seconds" ros2 run bsig_ros bsig_bridge --ros-args -p method:=DeepfakeDetection -p logits:=true \
    -r __node:=bsig_deepfake -r bsig/results:=bsig/deepfake &
timeout -s INT "$seconds" ros2 run bsig_ros bsig_affect &
timeout -s INT "$((seconds - 2))" ros2 bag record -s mcap -o "$results_bag" /bsig/results /bsig/affect /bsig/deepfake /diagnostics &
sleep 4
timeout "$((seconds - 5))" ros2 bag play -r 1 --delay 3 "$audio_bag" &
wait
