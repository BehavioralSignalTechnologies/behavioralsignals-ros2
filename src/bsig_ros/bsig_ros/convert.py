import math

from rcl_interfaces.msg import ParameterDescriptor

BYTES_PER_SAMPLE = 2  # signed 16-bit mono


def to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return math.nan


def to_seconds(s):
    v = to_float(s)
    return 0.0 if math.isnan(v) else v


def chunk_size_bytes(sample_rate, chunk_ms):
    return max(int(sample_rate * chunk_ms / 1000), 1) * BYTES_PER_SAMPLE

EXPECTED_AUDIO_FORMAT = {'channels': 1, 'sample_format': 'S16LE', 'coding_format': 'wave'}


def audio_info_problem(info):
    """Returns why an AudioInfo does not describe mono S16LE PCM, or '' when it does."""
    if info.sample_rate <= 0:
        return f'sample_rate is {info.sample_rate}'
    for field, want in EXPECTED_AUDIO_FORMAT.items():
        got = getattr(info, field)
        if got != want:
            return f'{field} is {got!r}, expected {want!r}'
    return ''


def declare_float(node, name, default):
    """Declares a float parameter that also accepts an integer value such as `-p name:=30`."""
    return float(node.declare_parameter(name, default, ParameterDescriptor(dynamic_typing=True)).value)
