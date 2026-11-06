"""Stand-in for the TV app (protocol v2): pairing, trusted devices, AES-GCM, writes video/audio to files.

    python tools/test_receiver.py out.h264 [--port 5000] [--seconds 10] [--state rx_state.json]
Run from the repo root with the sender venv (needs the sender package + cryptography).
"""
import argparse
import hmac
import json
import os
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sender"))
from airscreen_sender.networking import crypto  # noqa: E402
from airscreen_sender.networking import protocol as P  # noqa: E402


# Pretend to be a 4K TV with a decoder that does 4K30 / 1080p60 on Ethernet.
CAPS = {"video": {"modes": [{"w": 3840, "h": 2160, "fps": 30}, {"w": 1920, "h": 1080, "fps": 60}]},
        "display": {"w": 3840, "h": 2160, "refresh": 60}, "net": {"type": "ethernet", "link_mbps": 1000},
        "audio": {"max_channels": 2, "rates": [48000]}}


def recv_exact(c, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = c.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    return bytes(buf)


def read_msg(c):
    raw = recv_exact(c, P.HEADER_SIZE)
    h = P.parse_header(raw)
    return raw, h, recv_exact(c, h.length)


def send_json(c, typ, seq, obj):
    c.sendall(P.pack_message(typ, seq, 0, json.dumps(obj).encode()))


def authenticate(c, state, code):
    """Receiver side of the handshake. Returns the session MediaCipher."""
    _, h, body = read_msg(c)
    assert h.type == P.TYPE_AUTH_REQUEST, "expected AUTH_REQUEST"
    req = json.loads(body)
    dev, ns = req["device_id"], bytes.fromhex(req["ns"])
    nr = crypto.new_nonce()
    trusted_key = bytes.fromhex(state["devices"][dev]) if dev in state["devices"] else None
    send_json(c, P.TYPE_AUTH_CHALLENGE, 0, {"nr": nr.hex(), "receiver_id": state["id"], "name": "Test receiver",
                                            "trusted": trusted_key is not None, "caps": CAPS})
    _, h, body = read_msg(c)
    assert h.type == P.TYPE_AUTH_PROOF
    proof = json.loads(body)
    if proof["mode"] == "trusted" and trusted_key:
        secret = trusted_key
    elif proof["mode"] == "pair":
        secret = code
    else:
        send_json(c, P.TYPE_AUTH_FAIL, 1, {"reason": "not paired"})
        raise PermissionError("untrusted device")
    if not hmac.compare_digest(bytes.fromhex(proof["proof"]), crypto.client_proof(secret, ns, nr, dev)):
        send_json(c, P.TYPE_AUTH_FAIL, 1, {"reason": "bad proof"})
        raise PermissionError("bad proof")
    send_json(c, P.TYPE_AUTH_OK, 1, {"proof": crypto.server_proof(secret, ns, nr).hex()})
    if proof["mode"] == "pair":
        state["devices"][dev] = crypto.device_key(secret, ns, nr).hex()
        print("paired", dev, flush=True)
    return crypto.MediaCipher(crypto.session_key(secret, ns, nr))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--seconds", type=float, default=0, help="stop after N seconds (0 = until BYE)")
    ap.add_argument("--state", default="rx_state.json")
    a = ap.parse_args()
    try:
        state = json.load(open(a.state))
    except OSError:
        state = {"id": os.urandom(6).hex(), "devices": {}}
    code_text = crypto.new_pairing_code()
    code = code_text.encode()
    print("pairing code:", crypto.format_code(code_text), flush=True)

    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", a.port))
    srv.listen(1)
    print(f"waiting on :{a.port}", flush=True)
    c, addr = srv.accept()
    print("sender", addr, flush=True)
    frames = keys = abytes = vbytes = apackets = 0
    t0 = time.time()
    expect_seq = 0
    cipher = None
    try:
        cipher = authenticate(c, state, code)
        json.dump(state, open(a.state, "w"))
        with open(a.out, "wb") as f, open(a.out + ".opus.bin", "wb") as af:
            while not a.seconds or time.time() - t0 < a.seconds:
                raw, h, body = read_msg(c)
                assert h.seq == expect_seq, f"seq gap {expect_seq}->{h.seq}"
                expect_seq += 1
                payload = cipher.open(h.seq, body, raw)  # raises InvalidTag on tampering
                if h.type == P.TYPE_HELLO:
                    print("hello", json.loads(payload), flush=True)
                elif h.type == P.TYPE_VIDEO:
                    f.write(payload)
                    frames += 1
                    keys += h.flags & 1
                    vbytes += len(payload)
                elif h.type == P.TYPE_AUDIO:
                    af.write(len(payload).to_bytes(2, "big") + payload)
                    apackets += 1
                    abytes += len(payload)
                elif h.type == P.TYPE_BYE:
                    print("bye")
                    break
    except (ConnectionError, PermissionError) as e:
        print("ended:", e)
    dt = max(time.time() - t0, 1e-6)
    print(f"video {frames} frames ({keys} key) {vbytes * 8 / dt / 1e6:.1f} Mbit/s | "
          f"audio {apackets} packets ({apackets / dt:.1f}/s) {abytes * 8 / dt / 1e3:.0f} kbit/s | {dt:.1f}s")


if __name__ == "__main__":
    main()
