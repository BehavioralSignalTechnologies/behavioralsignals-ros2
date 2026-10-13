import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

from bsig_msgs.msg import Affect, StreamResult

from .convert import declare_float
from .smoothing import AffectTracker


def seconds(stamp):
    return stamp.sec + stamp.nanosec * 1e-9


class BsigAffect(Node):
    def __init__(self):
        super().__init__('bsig_affect')
        self.tracker = AffectTracker(declare_float(self, 'time_constant_s', 3.0))
        self.pub = self.create_publisher(Affect, 'bsig/affect', 10)
        self.create_subscription(StreamResult, 'bsig/results', self.on_result, 10)

    def on_result(self, msg):
        changed = [self.tracker.update(r, seconds(r.end)) for r in msg.results]
        if any(changed) and self.tracker.ready():
            self.pub.publish(self.affect_msg(msg.header))

    def affect_msg(self, header):
        t = self.tracker
        return Affect(
            header=header,
            valence=t.values['positivity'],
            arousal=t.values['strength'],
            emotion=t.emotion,
            emotion_posterior=t.emotion_posterior,
        )


def main():
    rclpy.init()
    node = BsigAffect()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
