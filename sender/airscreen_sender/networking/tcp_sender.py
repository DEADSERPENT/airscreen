"""TCP sender with a bounded queue. Drops to the next keyframe when the network falls behind."""
from __future__ import annotations

import queue
import socket
import threading
import time

from .protocol import (FLAG_KEYFRAME, TYPE_BYE, TYPE_HELLO, TYPE_VIDEO, hello_payload, pack_message)

QUEUE_LIMIT = 30  # ~1 s at 30 fps


class TcpSender:
    def __init__(self, ip: str, port: int, width: int, height: int, fps: int) -> None:
        self._sock = socket.create_connection((ip, port), timeout=5)
        self._sock.settimeout(10)  # a stalled receiver surfaces as an error instead of hanging
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._q: queue.Queue[bytes | None] = queue.Queue(maxsize=QUEUE_LIMIT)
        self._seq = 0
        self._t0 = time.monotonic()
        self._need_key = True       # start (and resume after drops) on a keyframe
        self.dropped = 0
        self.sent_bytes = 0
        self.error: Exception | None = None
        self._send_raw(pack_message(TYPE_HELLO, self._next_seq(), 0, hello_payload(width, height, fps)))
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _next_seq(self) -> int:
        s = self._seq
        self._seq += 1
        return s

    def _send_raw(self, data: bytes) -> None:
        self._sock.sendall(data)
        self.sent_bytes += len(data)

    def submit(self, au: bytes, keyframe: bool) -> None:
        """Called from the encoder thread. Never blocks."""
        if self.error:
            return  # session loop notices net.error and shuts down
        if self._need_key and not keyframe:
            self.dropped += 1
            return
        pts_us = int((time.monotonic() - self._t0) * 1_000_000)
        msg = pack_message(TYPE_VIDEO, self._next_seq(), pts_us, au, FLAG_KEYFRAME if keyframe else 0)
        try:
            self._q.put_nowait(msg)
            self._need_key = False
        except queue.Full:
            # Network is behind: flush stale data and wait for the next keyframe.
            self.dropped += self._q.qsize() + 1
            while True:
                try:
                    self._q.get_nowait()
                except queue.Empty:
                    break
            self._need_key = True

    def _run(self) -> None:
        try:
            while True:
                msg = self._q.get()
                if msg is None:
                    return
                self._send_raw(msg)
        except Exception as e:  # connection lost / timed out
            self.error = e

    def close(self) -> None:
        try:
            if not self.error:
                self._q.put(None, timeout=1)
                self._thread.join(timeout=3)
                self._send_raw(pack_message(TYPE_BYE, self._next_seq(), 0))
        except Exception:
            pass
        finally:
            try:
                self._sock.close()
            except OSError:
                pass
