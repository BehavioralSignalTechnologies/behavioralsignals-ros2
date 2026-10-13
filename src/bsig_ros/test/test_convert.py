import math
from types import SimpleNamespace as N

from bsig_ros.convert import audio_info_problem, chunk_size_bytes, to_float, to_seconds


def test_to_float_parses_api_strings():
    assert to_float('0.754') == 0.754


def test_to_float_is_nan_when_missing_or_empty():
    assert math.isnan(to_float(''))
    assert math.isnan(to_float(None))


def test_to_seconds_is_zero_when_missing():
    assert to_seconds('') == 0.0
    assert to_seconds('1.5') == 1.5


def test_chunk_size_is_250ms_of_16bit_mono():
    assert chunk_size_bytes(16000, 250) == 8000


def test_chunk_size_is_never_zero():
    assert chunk_size_bytes(1, 250) == 2


def info(**overrides):
    fields = dict(channels=1, sample_rate=16000, sample_format='S16LE', coding_format='wave')
    return N(**{**fields, **overrides})


def test_valid_audio_info_has_no_problem():
    assert audio_info_problem(info()) == ''


def test_audio_info_problems_are_named():
    assert 'coding_format' in audio_info_problem(info(coding_format='mp3'))
    assert 'channels' in audio_info_problem(info(channels=2))
    assert 'sample_rate' in audio_info_problem(info(sample_rate=0))
