class Chunker:
    """Cuts a byte stream into fixed-size chunks."""

    def __init__(self, size):
        self.size = size
        self.buf = bytearray()

    def feed(self, data):
        self.buf.extend(data)
        chunks = []
        while len(self.buf) >= self.size:
            chunks.append(bytes(self.buf[: self.size]))
            del self.buf[: self.size]
        return chunks
