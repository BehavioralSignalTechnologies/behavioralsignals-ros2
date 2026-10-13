import queue
import threading

from .chunker import Chunker
from .convert import chunk_size_bytes

QUEUE_SECONDS = 30


class Session:
    """Audio for one gRPC stream: its chunks and its time origin."""

    def __init__(self, sample_rate, chunk_ms):
        self.sample_rate = sample_rate
        self.chunker = Chunker(chunk_size_bytes(sample_rate, chunk_ms))
        self.queue = queue.Queue(maxsize=QUEUE_SECONDS * 1000 // chunk_ms)
        self.closed = threading.Event()
        self.t0 = None
        self.call = None

    def add(self, stamp, data):
        """Queues the audio and returns how many chunks did not fit."""
        if self.t0 is None:
            self.t0 = stamp
        dropped = 0
        for chunk in self.chunker.feed(data):
            try:
                self.queue.put_nowait(chunk)
            except queue.Full:
                dropped += 1
        return dropped

    def audio(self):
        while not self.closed.is_set():
            try:
                yield self.queue.get(timeout=0.5)
            except queue.Empty:
                continue

    def attach(self, call):
        """Remembers the gRPC call so closing the session can cancel it."""
        self.call = call
        if self.closed.is_set():
            call.cancel()

    def close(self):
        self.closed.set()
        if self.call:
            self.call.cancel()
