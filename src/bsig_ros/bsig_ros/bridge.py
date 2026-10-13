import os
import sys
import threading
import time

import grpc
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time

from audio_common_msgs.msg import AudioDataStamped, AudioInfo
from bsig_msgs.msg import StreamResult
from diagnostic_msgs.msg import DiagnosticArray

from . import api_pb2 as pb
from . import api_pb2_grpc as pb_grpc
from .convert import audio_info_problem, declare_float
from .diagnostics import Stats, status_msg
from .mapping import stream_result_msg
from .session import Session

SOURCES = {'StreamAudio': 'behavioral', 'DeepfakeDetection': 'deepfake'}
LEVELS = {'segment': pb.segment, 'utterance': pb.utterance}
RELIABILITY = {'reliable': ReliabilityPolicy.RELIABLE, 'best_effort': ReliabilityPolicy.BEST_EFFORT}
WATCHDOG_S = 10.0
IDLE_CHECK_S = 0.5
DIAGNOSTICS_PERIOD_S = 1.0
INFO_WAIT_S = 2.0
INITIAL_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0
GRPC_POLL_S = 0.25  # grpc polls connectivity every 0.2 s; closing the channel sooner raises in its thread
CHUNK_MS_RANGE = (100, 500)
REJECTED_CREDENTIALS = (grpc.StatusCode.PERMISSION_DENIED, grpc.StatusCode.UNAUTHENTICATED)


def read_credentials():
    try:
        cid, key = os.environ['BEHAVIORALSIGNALS_CID'], os.environ['BEHAVIORALSIGNALS_API_KEY']
    except KeyError as e:
        raise RuntimeError(f'environment variable {e.args[0]} is not set') from None
    if not cid.isdigit():
        raise RuntimeError('BEHAVIORALSIGNALS_CID must be a number')
    return int(cid), key


def positive(value, name):
    if value <= 0:
        raise ValueError(f'{name} must be positive, got {value!r}')
    return value


def non_negative(value, name):
    if value < 0:
        raise ValueError(f'{name} must not be negative, got {value!r}')
    return value


def in_range(value, bounds, name):
    low, high = bounds
    if not low <= value <= high:
        raise ValueError(f'{name} must be between {low} and {high}, got {value!r}')
    return value


def describe(error):
    if isinstance(error, grpc.RpcError):
        return f'{error.code().name}: {error.details()}'
    return repr(error)


def choose(value, allowed, name):
    if value not in allowed:
        raise ValueError(f'{name} must be one of {sorted(allowed)}, got {value!r}')
    return value


class BsigBridge(Node):
    def __init__(self):
        super().__init__('bsig_bridge')
        p = self.declare_parameter
        self.endpoint = p('endpoint', 'streaming.behavioralsignals.com:443').value
        self.use_tls = p('use_tls', True).value
        self.method = choose(p('method', 'StreamAudio').value, SOURCES, 'method')
        self.level = choose(p('level', 'all').value, ('all', *LEVELS), 'level')
        self.logits = p('logits', False).value
        self.param_sample_rate = positive(p('sample_rate', 16000).value, 'sample_rate')
        self.chunk_ms = in_range(p('chunk_ms', 250).value, CHUNK_MS_RANGE, 'chunk_ms')
        self.idle_timeout_s = non_negative(declare_float(self, 'idle_timeout_s', 0.0), 'idle_timeout_s')
        reliability = choose(p('audio_qos_reliability', 'reliable').value, RELIABILITY, 'audio_qos_reliability')
        self.cid, self.key = read_credentials()

        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.info_seen = threading.Event()
        self.session = None
        self.info = None
        self.format_problem = ''
        self.audio_seen = False
        self.last_audio = time.monotonic()
        self.idle = bool(self.idle_timeout_s)
        self.stats = Stats()

        audio_qos = QoSProfile(depth=100, reliability=RELIABILITY[reliability], history=HistoryPolicy.KEEP_LAST)
        info_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(AudioDataStamped, 'audio_stamped', self.on_audio, audio_qos)
        self.create_subscription(AudioInfo, 'audio_info', self.on_info, info_qos)
        self.pub = self.create_publisher(StreamResult, 'bsig/results', 10)
        self.diagnostics_pub = self.create_publisher(DiagnosticArray, 'diagnostics', 10)
        self.create_timer(WATCHDOG_S, self.check_audio_arriving)
        self.create_timer(DIAGNOSTICS_PERIOD_S, self.publish_diagnostics)
        if self.idle_timeout_s:
            self.create_timer(IDLE_CHECK_S, self.check_idle)
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def sample_rate(self):
        return self.info.sample_rate if self.info else self.param_sample_rate

    def on_info(self, info):
        with self.lock:
            self.info = info
            self.format_problem = audio_info_problem(info)
            if self.format_problem:
                self.get_logger().error(f'unsupported audio, nothing is sent: {self.format_problem}')
            if self.session and self.session.sample_rate != info.sample_rate:
                self.session.close()
        self.info_seen.set()

    def on_audio(self, msg):
        self.audio_seen = True
        self.last_audio = time.monotonic()
        if msg.header.stamp.sec == 0 and msg.header.stamp.nanosec == 0:
            self.get_logger().warning('audio header stamp is zero, result times will be wrong', once=True)
        with self.lock:
            if self.format_problem:
                self.stats.dropped_format += 1
                return
            if self.session is None or self.session.closed.is_set():
                self.stats.dropped_idle += 1
                self.get_logger().warning(f'no stream open, audio dropped ({self.stats.dropped_idle} messages)', throttle_duration_sec=5)
                return
            dropped = self.session.add(Time.from_msg(msg.header.stamp), msg.audio.data)
            self.stats.note_queue(self.session.queue.qsize())
        if dropped:
            self.stats.dropped_full += dropped
            self.get_logger().warning(f'queue full, {self.stats.dropped_full} chunks dropped, restarting the stream')
            self.restart_stream()

    def restart_stream(self):
        """Ends the current stream; a gap in the audio would shift every later result time."""
        with self.lock:
            if self.session:
                self.session.close()

    def check_idle(self):
        """Ends the stream after idle_timeout_s without audio; the next one opens when audio returns."""
        if not self.idle and time.monotonic() - self.last_audio > self.idle_timeout_s:
            self.idle = True
            self.get_logger().info(f'no audio for {self.idle_timeout_s:g} s, ending the stream until audio returns')
            self.restart_stream()

    def check_audio_arriving(self):
        if not self.audio_seen:
            self.get_logger().warning(f'no audio on {self.resolve_topic_name("audio_stamped")} for {WATCHDOG_S:.0f} s')
        self.stats.audio_stalled = not self.audio_seen
        self.audio_seen = False

    def publish_diagnostics(self):
        array = DiagnosticArray()
        array.header.stamp = self.get_clock().now().to_msg()
        array.status = [status_msg(self.get_fully_qualified_name(), self.stats, self.format_problem)]
        self.diagnostics_pub.publish(array)

    def channel(self):
        if self.use_tls:
            return grpc.secure_channel(self.endpoint, grpc.ssl_channel_credentials())
        return grpc.insecure_channel(self.endpoint)

    def requests(self, session):
        cfg = pb.AudioConfig(encoding=pb.LINEAR_PCM, sample_rate_hertz=session.sample_rate)
        if self.level != 'all':
            cfg.level = LEVELS[self.level]
        if self.logits:
            cfg.logits = True
        yield pb.AudioStream(cid=self.cid, x_auth_token=self.key, config=cfg)
        for chunk in session.audio():
            yield pb.AudioStream(cid=self.cid, x_auth_token=self.key, audio_content=chunk)

    def stream_once(self, session):
        """Runs one stream until it ends or the session is closed."""
        with self.channel() as ch:
            ch.subscribe(self.on_connectivity, try_to_connect=True)
            call = getattr(pb_grpc.BehavioralStreamingApiStub(ch), self.method)(self.requests(session))
            session.attach(call)
            try:
                for resp in call:
                    self.publish(resp, session)
            finally:
                ch.unsubscribe(self.on_connectivity)
                self.stats.stream_open = False
                self.stop.wait(GRPC_POLL_S)

    def on_connectivity(self, state):
        self.stats.stream_open = state == grpc.ChannelConnectivity.READY

    def publish(self, resp, session):
        self.stats.results += 1
        self.stats.error = ''
        received = self.get_clock().now().to_msg()
        self.pub.publish(stream_result_msg(resp, session.t0 or Time.from_msg(received), received, SOURCES[self.method]))

    def open_session(self):
        with self.lock:
            self.session = Session(self.sample_rate(), self.chunk_ms)
            self.stats.streams_opened += 1
            return self.session

    def close_session(self, session):
        with self.lock:
            session.close()
            self.session = None
            self.stats.stream_open = False
        unsent = session.queue.qsize()
        if unsent:
            self.stats.unsent += unsent
            self.get_logger().warning(f'stream ended, {unsent} queued chunks were not sent')

    def run(self):
        if not self.info_seen.wait(INFO_WAIT_S):
            self.get_logger().warning(f'no AudioInfo received, assuming mono S16LE at {self.param_sample_rate} Hz')
        backoff = INITIAL_BACKOFF_S
        while not self.stop.is_set() and not self.stats.fatal:
            if self.format_problem:
                self.stop.wait(INITIAL_BACKOFF_S)
                continue
            session = self.open_session()
            self.wait_for_audio(session)
            results_before = self.stats.results
            error = self.run_stream(session)
            healthy = error is None or self.stats.results > results_before
            self.close_session(session)
            if healthy:
                backoff = INITIAL_BACKOFF_S
                continue
            self.stop.wait(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_S)

    def wait_for_audio(self, session):
        """After an idle end, holds the new stream back until its first audio is queued."""
        while self.idle and not self.stop.is_set() and not session.closed.is_set() and session.queue.empty():
            self.stop.wait(0.05)
        self.idle = False

    def run_stream(self, session):
        """Runs one stream. Returns the error that ended it, or None when it ended on purpose."""
        try:
            self.stream_once(session)
        except Exception as e:
            if session.closed.is_set():
                return None
            self.note_error(e)
            return e
        return None

    def note_error(self, error):
        self.stats.error = describe(error)
        if isinstance(error, grpc.RpcError) and error.code() in REJECTED_CREDENTIALS:
            self.stats.fatal = True
            self.get_logger().error(f'credentials rejected, not retrying: {self.stats.error}')
        else:
            self.get_logger().error(f'stream closed: {self.stats.error}')

    def destroy_node(self):
        self.stop.set()
        with self.lock:
            if self.session:
                self.session.close()
        self.thread.join(timeout=2)
        super().destroy_node()


def main():
    rclpy.init()
    try:
        node = BsigBridge()
    except (RuntimeError, ValueError) as e:
        print(f'bsig_bridge: {e}', file=sys.stderr)
        rclpy.try_shutdown()
        sys.exit(1)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
