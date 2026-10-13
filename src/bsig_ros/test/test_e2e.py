"""Bridge and affect nodes against a fake API, over real ROS topics."""
import math
import threading
import time

import grpc
import pytest
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

from audio_common_msgs.msg import AudioDataStamped, AudioInfo
from bsig_msgs.msg import Affect, StreamResult
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from bsig_ros import api_pb2 as pb
from bsig_ros.affect import BsigAffect
from bsig_ros import bridge
from bsig_ros import session as session_module
from bsig_ros.bridge import BsigBridge

import fake_api

RATE = 8000
CHUNK_BYTES = RATE // 4 * 2  # 250 ms of S16LE mono
T_START = 100.0


def info(**overrides):
    fields = dict(channels=1, sample_rate=RATE, sample_format='S16LE', bitrate=0, coding_format='wave')
    return AudioInfo(**{**fields, **overrides})


class Feeder(Node):
    """Publishes AudioInfo, then one 250 ms message every 20 ms. Each message carries its index."""

    def __init__(self, audio_info, feed=True, reliability=ReliabilityPolicy.RELIABLE):
        super().__init__('feeder')
        latched = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.info_pub = self.create_publisher(AudioInfo, 'audio_info', latched)
        self.info_pub.publish(audio_info)
        self.pub = self.create_publisher(AudioDataStamped, 'audio_stamped', QoSProfile(depth=100, reliability=reliability))
        self.i = 0
        if feed:
            self.create_timer(0.02, self.send)

    def send(self):
        msg = AudioDataStamped()
        total = T_START + 0.25 * self.i
        msg.header.stamp.sec, msg.header.stamp.nanosec = int(total), int(round((total % 1) * 1e9))
        msg.audio.data = self.i.to_bytes(2, 'little') * (CHUNK_BYTES // 2)
        self.pub.publish(msg)
        self.i += 1


class Collector(Node):
    def __init__(self):
        super().__init__('collector')
        self.results, self.affects, self.diagnostics = [], [], []
        self.create_subscription(StreamResult, 'bsig/results', self.results.append, 10)
        self.create_subscription(Affect, 'bsig/affect', self.affects.append, 10)
        self.create_subscription(DiagnosticArray, 'diagnostics', self.diagnostics.append, 10)


class Rig:
    def __init__(self, api, audio_info, node_args=(), with_affect=True, **feeder_args):
        self.server, port = fake_api.start(api)
        rclpy.init(args=['--ros-args', '-p', f'endpoint:=localhost:{port}', '-p', 'use_tls:=false', *node_args])
        self.collector = Collector()
        nodes = [BsigBridge(), self.collector, Feeder(audio_info, **feeder_args)]
        if with_affect:
            nodes.append(BsigAffect())
        self.nodes = nodes
        self.executor = MultiThreadedExecutor(num_threads=4)
        for n in nodes:
            self.executor.add_node(n)
        threading.Thread(target=self.executor.spin, daemon=True).start()

    def wait_for(self, condition, timeout=15.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if condition():
                return True
            time.sleep(0.05)
        return False

    def close(self):
        self.executor.shutdown()
        for n in self.nodes:
            n.destroy_node()
        rclpy.shutdown()
        self.server.stop(0)


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv('BEHAVIORALSIGNALS_CID', '123')
    monkeypatch.setenv('BEHAVIORALSIGNALS_API_KEY', 'secret')


def stamp_seconds(t):
    return t.sec + t.nanosec * 1e-9


def streams_with_audio(api):
    return [s for s in api.streams if s.chunks]


def first_message_index(stream):
    return int.from_bytes(stream.chunks[0][:2], 'little')


def test_results_are_published_with_absolute_times_and_affect(env):
    api = fake_api.FakeApi()
    rig = Rig(api, info())
    try:
        assert rig.wait_for(lambda: rig.collector.results and rig.collector.affects)
        stream = streams_with_audio(api)[0]
        assert len(api.streams) == 1
        cfg = stream.first.config
        assert (stream.first.cid, stream.first.x_auth_token) == (123, 'secret')
        assert cfg.sample_rate_hertz == RATE and cfg.encoding == pb.LINEAR_PCM and not cfg.HasField('level')

        out = rig.collector.results[0]
        t0 = T_START + 0.25 * first_message_index(stream)
        segment, utterance = out.results[1], out.results[3]
        assert (out.source, out.pid) == ('behavioral', 42)
        assert (segment.task, segment.level, segment.final_label) == ('positivity', 'segment', 'positive')
        assert math.isclose(stamp_seconds(segment.start), t0 + 1.0, abs_tol=1e-6)
        assert math.isclose(stamp_seconds(segment.end), t0 + 3.0, abs_tol=1e-6)
        assert utterance.level == 'utterance'
        assert segment.predictions[0].posterior == pytest.approx(0.8)
        assert math.isnan(segment.predictions[0].logit)

        affect = rig.collector.affects[0]
        assert affect.valence == pytest.approx(0.7) and affect.arousal == pytest.approx(0.4)
        assert affect.emotion == 'happy'
    finally:
        rig.close()


def test_reconnect_opens_a_new_stream_with_a_new_time_origin(env):
    api = fake_api.FakeApi(end_first_stream_after_result=True)
    rig = Rig(api, info(), with_affect=False)
    try:
        assert rig.wait_for(lambda: len(rig.collector.results) >= 2, timeout=20)
        first, second = streams_with_audio(api)[:2]
        assert second.first.HasField('config')
        origins = [T_START + 0.25 * first_message_index(s) for s in (first, second)]
        assert origins[1] > origins[0]
        for out, t0 in zip(rig.collector.results[:2], origins):
            assert math.isclose(stamp_seconds(out.results[1].start), t0 + 1.0, abs_tol=1e-6)
    finally:
        rig.close()


def test_deepfake_method_publishes_deepfake_source(env):
    rig = Rig(fake_api.FakeApi(), info(), node_args=['-p', 'method:=DeepfakeDetection'], with_affect=False)
    try:
        assert rig.wait_for(lambda: rig.collector.results)
        out = rig.collector.results[0]
        assert out.source == 'deepfake' and out.results[0].task == 'deepfake'
    finally:
        rig.close()


def test_level_parameter_is_sent_in_config(env):
    api = fake_api.FakeApi()
    rig = Rig(api, info(), node_args=['-p', 'level:=utterance'], with_affect=False)
    try:
        assert rig.wait_for(lambda: streams_with_audio(api))
        assert all(s.first.config.level == pb.utterance for s in api.streams)
    finally:
        rig.close()


def test_logits_parameter_is_sent_in_config(env):
    api = fake_api.FakeApi()
    rig = Rig(api, info(), node_args=['-p', 'logits:=true'], with_affect=False)
    try:
        assert rig.wait_for(lambda: streams_with_audio(api))
        assert all(s.first.config.logits for s in api.streams)
        assert rig.wait_for(lambda: rig.collector.results)
        predictions = [p for r in rig.collector.results[0].results for p in r.predictions]
        assert predictions and all(p.logit == pytest.approx(1.5) for p in predictions)
    finally:
        rig.close()


def test_logits_are_off_by_default(env):
    api = fake_api.FakeApi()
    rig = Rig(api, info(), with_affect=False)
    try:
        assert rig.wait_for(lambda: streams_with_audio(api))
        assert not any(s.first.config.HasField('logits') for s in api.streams)
        assert rig.wait_for(lambda: rig.collector.results)
        assert all(math.isnan(p.logit) for r in rig.collector.results[0].results for p in r.predictions)
    finally:
        rig.close()


def test_level_segment_is_sent_as_present_in_config(env):
    api = fake_api.FakeApi()
    rig = Rig(api, info(), node_args=['-p', 'level:=segment'], with_affect=False)
    try:
        assert rig.wait_for(lambda: streams_with_audio(api))
        config = api.streams[-1].first.config
        assert config.HasField('level') and config.level == pb.segment
    finally:
        rig.close()


def test_best_effort_audio_is_received_with_best_effort_parameter(env):
    api = fake_api.FakeApi()
    rig = Rig(api, info(), node_args=['-p', 'audio_qos_reliability:=best_effort'], with_affect=False,
              reliability=ReliabilityPolicy.BEST_EFFORT)
    try:
        assert rig.wait_for(lambda: rig.collector.results)
    finally:
        rig.close()


def test_sample_rate_change_restarts_the_stream(env):
    api = fake_api.FakeApi()
    rig = Rig(api, info(), with_affect=False)
    try:
        assert rig.wait_for(lambda: streams_with_audio(api))
        rig.nodes[2].info_pub.publish(info(sample_rate=16000))
        assert rig.wait_for(lambda: any(s.first.config.sample_rate_hertz == 16000 for s in api.streams))
    finally:
        rig.close()


def test_full_queue_drops_are_counted_and_restart_the_stream(env, monkeypatch):
    monkeypatch.setattr(session_module, 'QUEUE_SECONDS', 1)
    monkeypatch.setattr(session_module.Session, 'audio', stalled_audio)
    api = fake_api.FakeApi()
    rig = Rig(api, info(), with_affect=False)
    try:
        assert rig.wait_for(lambda: rig.nodes[0].stats.dropped_full > 0 and len(api.streams) >= 2)
    finally:
        rig.close()


def stalled_audio(self):
    self.closed.wait()
    return iter(())


def last_status(rig):
    status = rig.collector.diagnostics[-1].status[0]
    return status, {kv.key: kv.value for kv in status.values}


def test_diagnostics_report_a_healthy_stream(env):
    api = fake_api.FakeApi()
    rig = Rig(api, info(), with_affect=False)
    try:
        assert rig.wait_for(lambda: rig.collector.diagnostics and last_status(rig)[1]['results'] != '0')
        status, values = last_status(rig)
        assert status.level == DiagnosticStatus.OK
        assert values['stream_open'] == 'True' and int(values['streams_opened']) >= 1
        assert int(values['queue_high_water']) >= 1
    finally:
        rig.close()


def test_diagnostics_warn_when_no_audio_arrives(env, monkeypatch):
    monkeypatch.setattr(bridge, 'WATCHDOG_S', 0.3)
    api = fake_api.FakeApi()
    rig = Rig(api, info(), with_affect=False, feed=False)
    try:
        assert rig.wait_for(lambda: rig.collector.diagnostics and last_status(rig)[0].message == 'no audio')
        assert last_status(rig)[0].level == DiagnosticStatus.WARN
    finally:
        rig.close()


def test_diagnostics_error_on_unsupported_audio(env):
    api = fake_api.FakeApi()
    rig = Rig(api, info(coding_format='mp3'), with_affect=False)
    try:
        assert rig.wait_for(lambda: rig.collector.diagnostics and last_status(rig)[0].level == DiagnosticStatus.ERROR)
    finally:
        rig.close()


def test_unsupported_audio_format_sends_no_audio(env):
    api = fake_api.FakeApi()
    rig = Rig(api, info(coding_format='mp3'), with_affect=False)
    try:
        assert rig.wait_for(lambda: rig.nodes[0].stats.dropped_format > 0)
        time.sleep(1.5)
        assert api.streams == []
    finally:
        rig.close()


def test_missing_credentials_fail_at_startup(monkeypatch):
    monkeypatch.delenv('BEHAVIORALSIGNALS_CID', raising=False)
    rclpy.init()
    try:
        with pytest.raises(RuntimeError, match='BEHAVIORALSIGNALS_CID'):
            BsigBridge()
    finally:
        rclpy.shutdown()


def diagnostics_message(rig):
    return rig.collector.diagnostics[-1].status[0].message


def test_rejected_credentials_stop_the_bridge_and_are_shown(env):
    api = fake_api.FakeApi(abort_code=grpc.StatusCode.PERMISSION_DENIED)
    rig = Rig(api, info(), with_affect=False)
    try:
        assert rig.wait_for(lambda: rig.collector.diagnostics
                            and last_status(rig)[0].level == DiagnosticStatus.ERROR
                            and 'PERMISSION_DENIED' in diagnostics_message(rig))
        assert 'rejected by the fake' in diagnostics_message(rig)
        time.sleep(2.5)
        assert len(api.streams) == 1
    finally:
        rig.close()


def test_other_errors_are_shown_and_retried(env):
    api = fake_api.FakeApi(abort_code=grpc.StatusCode.UNAVAILABLE)
    rig = Rig(api, info(), with_affect=False)
    try:
        assert rig.wait_for(lambda: len(api.streams) >= 2)
        assert rig.wait_for(lambda: rig.collector.diagnostics and 'UNAVAILABLE' in diagnostics_message(rig))
        assert last_status(rig)[0].level == DiagnosticStatus.WARN
    finally:
        rig.close()


def test_backoff_restarts_after_a_stream_that_gave_results(env):
    api = fake_api.FakeApi(abort_code=grpc.StatusCode.UNAVAILABLE, abort_after_result=True)
    rig = Rig(api, info(), with_affect=False)
    try:
        assert rig.wait_for(lambda: len(api.streams) >= 4, timeout=20)
        opened = [s.opened for s in api.streams[:4]]
        assert max(b - a for a, b in zip(opened, opened[1:])) < 0.9
    finally:
        rig.close()


@pytest.mark.parametrize('chunk_ms', [50, 1000])
def test_chunk_ms_outside_100_to_500_is_refused(env, chunk_ms):
    rclpy.init(args=['--ros-args', '-p', f'chunk_ms:={chunk_ms}'])
    try:
        with pytest.raises(ValueError, match='chunk_ms'):
            BsigBridge()
    finally:
        rclpy.shutdown()


def test_stream_ends_when_idle_and_the_next_one_keeps_the_first_audio(env):
    api = fake_api.FakeApi()
    rig = Rig(api, info(), node_args=['-p', 'idle_timeout_s:=1.0'], with_affect=False, feed=False)
    try:
        time.sleep(3.0)
        assert api.streams == []
        feeder = rig.nodes[2]
        feeder.create_timer(0.02, feeder.send)
        assert rig.wait_for(lambda: len(api.streams) == 1 and api.streams[0].chunks)
        assert first_message_index(api.streams[0]) == 0
    finally:
        rig.close()


def test_negative_idle_timeout_is_refused(env):
    rclpy.init(args=['--ros-args', '-p', 'idle_timeout_s:=-1.0'])
    try:
        with pytest.raises(ValueError, match='idle_timeout_s'):
            BsigBridge()
    finally:
        rclpy.shutdown()


def test_integer_values_are_accepted_for_the_float_parameters(env):
    rclpy.init(args=['--ros-args', '-p', 'idle_timeout_s:=30', '-p', 'time_constant_s:=5'])
    try:
        bridge, affect = BsigBridge(), BsigAffect()
        assert bridge.idle_timeout_s == 30.0
        bridge.destroy_node()
        affect.destroy_node()
    finally:
        rclpy.shutdown()


def test_non_numeric_cid_is_refused_with_a_plain_message(monkeypatch):
    monkeypatch.setenv('BEHAVIORALSIGNALS_CID', 'abc')
    monkeypatch.setenv('BEHAVIORALSIGNALS_API_KEY', 'secret')
    rclpy.init()
    try:
        with pytest.raises(RuntimeError, match='BEHAVIORALSIGNALS_CID must be a number'):
            BsigBridge()
    finally:
        rclpy.shutdown()


def test_held_stream_survives_a_sample_rate_change(env):
    api = fake_api.FakeApi()
    rig = Rig(api, info(), node_args=['-p', 'idle_timeout_s:=1.0'], with_affect=False, feed=False)
    try:
        time.sleep(1.5)
        feeder = rig.nodes[2]
        feeder.info_pub.publish(info(sample_rate=RATE // 2))
        time.sleep(0.5)
        feeder.create_timer(0.02, feeder.send)
        assert rig.wait_for(lambda: any(s.chunks for s in api.streams))
    finally:
        rig.close()
