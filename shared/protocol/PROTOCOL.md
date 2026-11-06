# AirScreen wire protocol — version 1

Transport: a single TCP connection. The **receiver (TV) listens** (default port `5000`);
the **sender (Windows) connects**. Trusted test LAN only: v1 has no authentication and no
encryption (see blueprint §12; secure pairing and WebRTC arrive in later versions).

All integers are big-endian. Every message is a 24-byte header followed by `length` payload bytes.

```
offset size field
0      4    magic        ASCII "ASCR"
4      1    version      1
5      1    type         1 HELLO, 2 VIDEO, 3 BYE
6      1    flags        bit0 = keyframe (VIDEO only)
7      1    reserved     0
8      4    seq          per-connection message counter, starts at 0
12     8    pts_us       presentation timestamp, microseconds since stream start
20     4    length       payload size in bytes (max 8 MiB)
```

## Messages

| type | name  | payload |
|------|-------|---------|
| 1    | HELLO | UTF-8 JSON, first message: `{"codec":"h264","width":1920,"height":1080,"fps":30}` |
| 2    | VIDEO | one H.264 access unit, Annex B (start-code delimited). Keyframes carry SPS+PPS inline. |
| 3    | BYE   | empty. Sender is stopping cleanly. |

## Receiver rules

- Reject (close the connection) on bad magic, unsupported version, unknown type, or `length` above the limit.
- HELLO must be the first message; `codec` must be `h264`; `width`/`height` must be 16..8192, `fps` 1..240.
- Do not feed the decoder until the first keyframe has arrived.
- Malformed data must never crash the receiver; drop the session and return to "waiting".

## Sender rules

- Bounded send queue. If the network cannot keep up, drop access units and resume at the next keyframe
  (never send a P-frame whose reference was dropped).
- Keyframe at least once per second.
