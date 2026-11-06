"""Stand-in for the TV app: accepts a sender, validates the protocol, writes the H.264 stream to a file.

    python tools/test_receiver.py out.h264 [--port 5000] [--seconds 10]
Then verify with ffprobe / ffplay on out.h264.
"""
import argparse
import json
import socket
import struct
import time

HEADER = struct.Struct(">4sBBBBIQI")


def recv_exact(c, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = c.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    return bytes(buf)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--seconds", type=float, default=0, help="stop after N seconds (0 = until BYE)")
    a = ap.parse_args()
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", a.port))
    srv.listen(1)
    print(f"waiting on :{a.port}", flush=True)
    c, addr = srv.accept()
    print("sender", addr, flush=True)
    frames = keys = nbytes = 0
    t0 = time.time()
    expect_seq = 0
    with open(a.out, "wb") as f:
        try:
            while not a.seconds or time.time() - t0 < a.seconds:
                magic, ver, typ, flags, _, seq, pts, ln = HEADER.unpack(recv_exact(c, HEADER.size))
                assert magic == b"ASCR" and ver == 1 and ln <= 8 << 20, "protocol violation"
                assert seq == expect_seq, f"seq gap {expect_seq}->{seq}"
                expect_seq += 1
                payload = recv_exact(c, ln)
                if typ == 1:
                    print("hello", json.loads(payload), flush=True)
                elif typ == 2:
                    f.write(payload)
                    frames += 1
                    keys += flags & 1
                    nbytes += ln
                elif typ == 3:
                    print("bye")
                    break
        except ConnectionError:
            print("connection closed")
    dt = max(time.time() - t0, 1e-6)
    print(f"{frames} frames ({keys} key) {nbytes / 1e6:.2f} MB in {dt:.1f}s = {frames / dt:.1f} fps {nbytes * 8 / dt / 1e6:.1f} Mbit/s")


if __name__ == "__main__":
    main()
