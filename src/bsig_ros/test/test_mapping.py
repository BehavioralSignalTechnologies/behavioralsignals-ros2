import math

from bsig_ros import api_pb2 as pb
from bsig_ros.mapping import prediction_msg


def test_logit_is_copied_when_returned():
    assert prediction_msg(pb.Prediction(label='a', posterior='0.9', logit='2.5')).logit == 2.5


def test_logit_is_nan_when_not_returned():
    assert math.isnan(prediction_msg(pb.Prediction(label='a', posterior='0.9')).logit)
