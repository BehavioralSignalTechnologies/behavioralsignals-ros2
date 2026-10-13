from rclpy.duration import Duration

from bsig_msgs.msg import InferenceResult, Prediction, StreamResult

from . import api_pb2 as pb
from .convert import to_float, to_seconds


def prediction_msg(p):
    return Prediction(
        label=p.label,
        posterior=to_float(p.posterior),
        logit=to_float(p.logit),
        score=to_float(p.score),
    )


def result_msg(r, t0):
    is_utterance = r.HasField('level') and r.level == pb.utterance
    return InferenceResult(
        task=r.task,
        final_label=r.final_label,
        level='utterance' if is_utterance else 'segment',
        start=(t0 + Duration(seconds=to_seconds(r.start_time))).to_msg(),
        end=(t0 + Duration(seconds=to_seconds(r.end_time))).to_msg(),
        predictions=[prediction_msg(p) for p in r.prediction],
    )


def stream_result_msg(resp, t0, received, source):
    out = StreamResult(source=source, pid=resp.pid, message_id=resp.message_id)
    out.header.stamp = received
    out.results = [result_msg(r, t0) for r in resp.result]
    return out
