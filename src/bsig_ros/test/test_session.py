from bsig_ros.session import Session


def test_first_stamp_is_the_time_origin():
    s = Session(sample_rate=8000, chunk_ms=250)
    s.add('t-first', b'\0' * 4000)
    s.add('t-second', b'\0' * 4000)
    assert s.t0 == 't-first'


def test_add_reports_chunks_that_do_not_fit():
    s = Session(sample_rate=8000, chunk_ms=250)
    capacity = s.queue.maxsize
    assert s.add('t', b'\0' * 4000 * (capacity + 3)) == 3


def test_audio_yields_queued_chunks_then_stops_when_closed():
    s = Session(sample_rate=8000, chunk_ms=250)
    s.add('t', b'\1' * 4000)
    chunks = s.audio()
    assert next(chunks) == b'\1' * 4000
    s.close()
    assert list(chunks) == []


class FakeCall:
    cancelled = False

    def cancel(self):
        self.cancelled = True


def test_closing_cancels_the_attached_call():
    s = Session(sample_rate=8000, chunk_ms=250)
    call = FakeCall()
    s.attach(call)
    s.close()
    assert call.cancelled


def test_attaching_to_a_closed_session_cancels_at_once():
    s = Session(sample_rate=8000, chunk_ms=250)
    s.close()
    call = FakeCall()
    s.attach(call)
    assert call.cancelled
