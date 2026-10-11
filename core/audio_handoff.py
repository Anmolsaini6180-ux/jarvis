"""Bounded capture handoff: one scheduled drain, no UI/DSP in PortAudio callback."""
from collections import deque
from threading import Lock

class AudioHandoff:
    def __init__(self, loop, consume, capacity=8):
        self.loop, self.consume, self.capacity = loop, consume, capacity
        self._frames = deque()
        self._lock = Lock()
        self._scheduled = False
        self.closed = False
        self.dropped = 0
        self.overflows = 0

    def offer(self, frame, context, overflow=False):
        # Copy while the PortAudio-owned buffer is valid. Everything else runs
        # on the asyncio thread, including DSP, Qt signals and wake inference feed.
        copied = frame.copy()
        with self._lock:
            if self.closed:return
            self.overflows += bool(overflow)
            if len(self._frames) >= self.capacity:
                self._frames.popleft()
                self.dropped += 1
            self._frames.append((copied, context))
            if self._scheduled:return
            self._scheduled = True
        try:self.loop.call_soon_threadsafe(self.drain)
        except RuntimeError:self.close()

    def drain(self):
        with self._lock:
            frames = list(self._frames)
            self._frames.clear()
            self._scheduled = False
        for frame, context in frames:
            if not self.closed:self.consume(frame, context)

    def close(self):
        with self._lock:
            self.closed = True
            self._frames.clear()
