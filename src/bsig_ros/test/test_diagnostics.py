from diagnostic_msgs.msg import DiagnosticStatus

from bsig_ros.diagnostics import Stats, status_msg


def test_new_bridge_without_stream_warns():
    assert status_msg('n', Stats(), '').level == DiagnosticStatus.WARN


def test_open_stream_is_ok():
    stats = Stats()
    stats.stream_open = True
    assert status_msg('n', stats, '').level == DiagnosticStatus.OK


def test_stalled_audio_warns_even_with_stream_open():
    stats = Stats()
    stats.stream_open, stats.audio_stalled = True, True
    assert status_msg('n', stats, '').message == 'no audio'


def test_format_problem_is_an_error_with_the_reason():
    status = status_msg('n', Stats(), 'channels is 2')
    assert status.level == DiagnosticStatus.ERROR and 'channels is 2' in status.message


def test_queue_high_water_keeps_the_maximum():
    stats = Stats()
    for depth in (3, 9, 4):
        stats.note_queue(depth)
    assert stats.queue_high_water == 9


def test_every_counter_is_published_as_text():
    keys = {kv.key for kv in status_msg('n', Stats(), '').values}
    assert {'streams_opened', 'results', 'dropped_idle', 'dropped_full', 'unsent', 'queue_high_water'} <= keys


def test_fatal_error_is_an_error_with_the_reason():
    stats = Stats()
    stats.fatal, stats.error = True, 'PERMISSION_DENIED: bad key'
    status = status_msg('n', stats, '')
    assert status.level == DiagnosticStatus.ERROR and 'PERMISSION_DENIED: bad key' in status.message


def test_error_without_open_stream_warns_with_the_reason():
    stats = Stats()
    stats.error = 'UNAVAILABLE: no route'
    status = status_msg('n', stats, '')
    assert status.level == DiagnosticStatus.WARN and 'UNAVAILABLE: no route' in status.message
