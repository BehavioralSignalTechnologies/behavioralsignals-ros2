from bsig_ros.chunker import Chunker


def test_emits_fixed_size_chunks():
    c = Chunker(4)
    assert c.feed(b'abcdefghij') == [b'abcd', b'efgh']


def test_keeps_remainder_for_next_feed():
    c = Chunker(4)
    c.feed(b'abcdef')
    assert c.feed(b'gh') == [b'efgh']


def test_nothing_until_a_full_chunk():
    assert Chunker(4).feed(b'ab') == []
