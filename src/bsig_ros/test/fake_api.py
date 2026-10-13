"""In-process fake of the streaming API for tests."""
import time
from concurrent import futures

import grpc

from bsig_ros import api_pb2 as pb
from bsig_ros import api_pb2_grpc as pb_grpc

RESULT_AFTER_CHUNKS = 4


def prediction(label, posterior):
    return pb.Prediction(label=label, posterior=str(posterior))


def inference(task, final_label, predictions, start, end, level):
    return pb.InferenceResult(
        id='1', task=task, final_label=final_label, start_time=str(start), end_time=str(end),
        prediction=predictions, level=level)


def behavioral_results():
    return [
        inference('emotion', 'happy', [prediction('happy', 0.8), prediction('sad', 0.2)], 1.0, 3.0, pb.segment),
        inference('positivity', 'positive', [prediction('positive', 0.8), prediction('negative', 0.1)], 1.0, 3.0, pb.segment),
        inference('strength', 'strong', [prediction('strong', 0.6), prediction('weak', 0.2)], 1.0, 3.0, pb.segment),
        inference('emotion', 'happy', [prediction('happy', 0.9)], 0.0, 3.5, pb.utterance),
    ]


def deepfake_results():
    return [inference('deepfake', 'bonafide', [prediction('bonafide', 0.97), prediction('spoofed', 0.03)], 0.0, 3.0, pb.utterance)]


def add_logits(results):
    for r in results:
        for p in r.prediction:
            p.logit = '1.5'


class Stream:
    def __init__(self, first):
        self.first = first
        self.chunks = []
        self.opened = time.monotonic()


class FakeApi(pb_grpc.BehavioralStreamingApiServicer):
    def __init__(self, end_first_stream_after_result=False, abort_code=None, abort_after_result=False):
        self.abort_code = abort_code
        self.abort_after_result = abort_after_result
        self.streams = []
        self.end_first = end_first_stream_after_result
        self.ended_one = False

    def StreamAudio(self, request_iterator, context):
        return self.serve(request_iterator, context, behavioral_results)

    def DeepfakeDetection(self, request_iterator, context):
        return self.serve(request_iterator, context, deepfake_results)

    def serve(self, requests, context, make_results):
        stream = Stream(next(requests))
        self.streams.append(stream)
        if self.abort_code and not self.abort_after_result:
            context.abort(self.abort_code, 'rejected by the fake')
        for req in requests:
            stream.chunks.append(req.audio_content)
            if len(stream.chunks) == RESULT_AFTER_CHUNKS:
                results = make_results()
                if stream.first.config.logits:
                    add_logits(results)
                yield pb.StreamResult(cid=stream.first.cid, pid=42, message_id=len(self.streams), result=results)
                if self.abort_code and self.abort_after_result:
                    context.abort(self.abort_code, 'link lost')
                if self.end_first and not self.ended_one:
                    self.ended_one = True
                    return


def start(api):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    pb_grpc.add_BehavioralStreamingApiServicer_to_server(api, server)
    port = server.add_insecure_port('localhost:0')
    server.start()
    return server, port
