#!/usr/bin/env bash
# Regenerates bsig_ros/api_pb2*.py from api.proto (source: Behavioral Signals API docs, "Proto file").
# api.proto is the same file as protos/api.proto in behavioralsignals-python v0.7.1 (commit f8d0b44), copied 2026-10-12.
# grpcio-tools 1.51.3 emits code that runs on protobuf 3.21 (Ubuntu 24.04 / ROS 2 Jazzy) and newer.
set -euo pipefail
cd "$(dirname "$0")/.."
docker run --rm -v "$PWD:/w" -w /w python:3.10-slim bash -c '
  pip install -q grpcio-tools==1.51.3 &&
  python -m grpc_tools.protoc -I protos --python_out=bsig_ros --grpc_python_out=bsig_ros protos/api.proto &&
  sed -i "s/^import api_pb2 as/from . import api_pb2 as/" bsig_ros/api_pb2_grpc.py &&
  chown -R '"$(id -u):$(id -g)"' bsig_ros protos'
