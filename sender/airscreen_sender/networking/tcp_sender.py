"""Authenticated, encrypted TCP sender with a bounded queue (drops to the next keyframe when behind)."""
from __future__ import annotations

import json
import queue
import socket
import threading
import time

from . import crypto
from .protocol import (FLAG_KEYFRAME, HEADER_SIZE, TYPE_AUDIO, TYPE_AUTH_CHALLENGE, TYPE_AUTH_FAIL, TYPE_AUTH_OK,
                       TYPE_AUTH_PROOF, TYPE_AUTH_REQUEST, TYPE_BYE, TYPE_HELLO, TYPE_VIDEO, ProtocolError,
                       hello_payload, pack_header, pack_message, parse_header)
from .trust_store import TrustStore

BEHIND_LIMIT = 40  # queued messages (~0.5 s of video+audio) before we declare the network behind


class AuthError(Exception):
    pass


class PairingRequired(Exception):
    def __init__(self, receiver_id: str, receiver_name: str) -> None:
        super().__init__(f"{receiver_name} needs its pair key")
        self.receiver_id = receiver_id
        self.receiver_name = receiver_name


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("receiver closed the connection")
        buf += chunk
    return bytes(buf)


def _read_control(sock: socket.socket, expect: tuple[int, ...]) -> tuple[int, dict]:
    h = parse_header(_recv_exact(sock, HEADER_SIZE))
    payload = _recv_exact(sock, h.length)
    if h.type not in expect:
        raise AuthError(f"unexpected message type {h.type} during handshake")
    try:
        return h.type, json.loads(payload) if payload else {}
    except json.JSONDecodeError as e:
        raise AuthError("malformed handshake message") from e


def handshake(sock: socket.socket, store: TrustStore, pair_key: str | None,
              on_verify=None) -> tuple[crypto.MediaCipher, str, dict]:
    """Trusted TV: prove the stored key. New TV: send the pair key + a key exchange; the TV pops up Allow/Deny and both
    screens show the same 4-digit number. Returns (cipher, receiver_name, receiver_capabilities)."""
    import hmac
    ns = crypto.new_nonce()
    sock.sendall(pack_message(TYPE_AUTH_REQUEST, 0, 0, json.dumps(
        {"device_id": store.device_id, "name": store.device_name, "ns": ns.hex()}).encode()))
    typ, ch = _read_control(sock, (TYPE_AUTH_CHALLENGE, TYPE_AUTH_FAIL))
    if typ == TYPE_AUTH_FAIL:
        raise AuthError(ch.get("reason", "receiver refused the connection"))
    nr = bytes.fromhex(ch["nr"])
    rid, rname = ch["receiver_id"], ch.get("name", "receiver")
    caps = ch.get("caps") or {}

    key = store.get_key(rid)
    if key is not None and not ch.get("trusted"):
        store.revoke(rid)  # the TV forgot us (revoked or reinstalled): pair again
        key = None

    if key is not None:  # ---- already paired
        sock.sendall(pack_message(TYPE_AUTH_PROOF, 1, 0, json.dumps(
            {"mode": "trusted", "proof": crypto.client_proof(key, ns, nr, store.device_id).hex()}).encode()))
        typ, ok = _read_control(sock, (TYPE_AUTH_OK, TYPE_AUTH_FAIL))
        if typ == TYPE_AUTH_FAIL:
            store.revoke(rid)
            raise AuthError(ok.get("reason", "authentication failed"))
        if not hmac.compare_digest(bytes.fromhex(ok["proof"]), crypto.server_proof(key, ns, nr)):
            raise AuthError("receiver failed to prove its identity")
        return crypto.MediaCipher(crypto.session_key(key, ns, nr)), rname, caps

    # ---- new TV: pair by key, approve on the TV
    if not pair_key:
        raise PairingRequired(rid, rname)
    try:
        k = crypto.normalize_key(pair_key)
    except ValueError as e:
        raise AuthError(str(e)) from e
    rpub = ch.get("rpub")
    if not rpub:
        raise AuthError("This TV app is too old for approval pairing. Update AirScreen on the TV.")
    priv, pub = crypto.new_keypair()
    shared = crypto.ecdh(priv, bytes.fromhex(rpub))
    if on_verify:
        on_verify(crypto.sas(shared, ns, nr))          # show the same number on the PC while the TV asks
    sock.sendall(pack_message(TYPE_AUTH_PROOF, 1, 0, json.dumps(
        {"mode": "request", "pub": pub.hex(), "key": k}).encode()))
    typ, ok = _read_control(sock, (TYPE_AUTH_OK, TYPE_AUTH_FAIL))
    if typ == TYPE_AUTH_FAIL:
        raise AuthError(ok.get("reason", "the TV refused the request"))
    if not hmac.compare_digest(bytes.fromhex(ok["proof"]), crypto.server_proof(shared, ns, nr)):
        raise AuthError("receiver failed to prove its identity")
    store.trust(rid, rname, crypto.device_key(shared, ns, nr))
    return crypto.MediaCipher(crypto.session_key(shared, ns, nr)), rname, caps


class TcpSender:
    def __init__(self, ip: str, port: int, store: TrustStore, pairing_code: str | None = None, on_verify=None) -> None:
        """Connect and authenticate. Call begin() once the stream settings are decided."""
        self._sock = socket.create_connection((ip, port), timeout=5)
        try:
            self._sock.settimeout(40)  # pairing waits for a person to press Allow on the TV
            self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._cipher, self.receiver_name, self.caps = handshake(self._sock, store, pairing_code, on_verify)
            self._sock.settimeout(10)  # streaming: a stalled receiver becomes an error instead of a hang
        except BaseException:
            self._sock.close()
            raise
        self._q: queue.Queue = queue.Queue()
        self._seq = 0  # touched only by the send thread (and begin() before it starts)
        self._t0 = time.monotonic()
        self._need_key = True  # start (and resume after drops) on a keyframe
        self.dropped = 0
        self.sent_bytes = 0
        self.net_ms: list[float] = []   # time a video frame waited in our queue + socket send
        self.error: Exception | None = None

    def begin(self, width: int, height: int, fps: int, audio_info: dict | None = None) -> None:
        self._send(TYPE_HELLO, 0, 0, hello_payload(width, height, fps, audio_info))
        self._thread = threading.Thread(target=self._run, name="net-send", daemon=True)
        self._thread.start()

    # --- producer side (encoder / audio threads); never blocks ---
    def _pts(self) -> int:
        return int((time.monotonic() - self._t0) * 1_000_000)

    def submit_video(self, au: bytes, keyframe: bool) -> None:
        if self.error:
            return
        if self._need_key and not keyframe:
            self.dropped += 1
            return
        if self._q.qsize() >= BEHIND_LIMIT:
            # Network is behind: discard stale video, keep audio, resume at next keyframe.
            keep = []
            while True:
                try:
                    item = self._q.get_nowait()
                except queue.Empty:
                    break
                if item is not None and item[0] == TYPE_AUDIO:
                    keep.append(item)
                else:
                    self.dropped += 1
            for item in keep:
                self._q.put(item)
            self.dropped += 1
            self._need_key = True
            return
        self._need_key = False
        self._q.put((TYPE_VIDEO, FLAG_KEYFRAME if keyframe else 0, self._pts(), au, time.monotonic()))

    def submit_audio(self, packet: bytes) -> None:
        if not self.error:
            self._q.put((TYPE_AUDIO, 0, self._pts(), packet))

    # --- send thread ---
    def _send(self, msg_type: int, flags: int, pts_us: int, payload: bytes) -> None:
        seq = self._seq
        self._seq += 1
        header = pack_header(msg_type, seq, pts_us, len(payload) + crypto.TAG_SIZE, flags)
        data = header + self._cipher.seal(seq, payload, header)
        self._sock.sendall(data)
        self.sent_bytes += len(data)

    def _run(self) -> None:
        try:
            while True:
                item = self._q.get()
                if item is None:
                    return
                self._send(*item[:4])
                if len(item) > 4 and len(self.net_ms) < 500:
                    self.net_ms.append((time.monotonic() - item[4]) * 1000)
        except Exception as e:  # connection lost / timed out
            self.error = e

    def close(self) -> None:
        try:
            if not self.error and getattr(self, "_thread", None):
                self._q.put(None)
                self._thread.join(timeout=3)
                self._send(TYPE_BYE, 0, 0, b"")
        except Exception:
            pass
        finally:
            try:
                self._sock.close()
            except OSError:
                pass
