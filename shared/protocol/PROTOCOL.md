# AirScreen wire protocol - version 2

Transport: one TCP connection. The **receiver (TV) listens** (default port `5000`, advertised as
`_airscreen._tcp` via mDNS with TXT `id`, `name`, `v`); the **sender (Windows) connects**.
All integers are big-endian. Every message = 24-byte header + `length` payload bytes.

```
0  4  magic "ASCR"      4  1  version (2)     5  1  type        6  1  flags (bit0 keyframe)
7  1  reserved          8  4  seq             12 8  pts_us      20 4  length (max 8 MiB; auth msgs max 4 KiB)
```

| type | name | direction | payload |
|---|---|---|---|
| 5 | AUTH_REQUEST | S->R | JSON `{device_id, name, ns}` (ns = 16 random bytes, hex) |
| 6 | AUTH_CHALLENGE | R->S | JSON `{nr, receiver_id, name, trusted, caps}` |
| 7 | AUTH_PROOF | S->R | JSON `{mode: "pair"\|"trusted", proof}` |
| 8 | AUTH_OK | R->S | JSON `{proof}` |
| 9 | AUTH_FAIL | R->S | JSON `{reason}` |
| 1 | HELLO | S->R | JSON `{codec:"h264", width, height, fps, audio?:{codec:"opus", rate:48000, channels, head:b64 OpusHead}}` |
| 2 | VIDEO | S->R | one H.264 Annex B access unit (SPS/PPS inline on keyframes) |
| 4 | AUDIO | S->R | one 20 ms Opus packet |
| 3 | BYE | S->R | empty |

Handshake messages are plaintext and use their own seq (0,1). After AUTH_OK, types 1-4 are sealed (below) and
seq restarts at 0.

## Security
- **Pairing (first time):** the TV shows a 16-character code (80 bits, single use, expires in 10 min, 5 wrong
  attempts lock pairing for 30 s and rotate the code). It is never transmitted. Sender and receiver prove knowledge with
  `HMAC-SHA256(code, "AirScreen-client"||ns||nr||device_id)` / `("AirScreen-server"||ns||nr)`, then both derive and store
  `device_key = HKDF(code, salt=ns||nr, info="AirScreen-device-key")`.
- **Trusted devices:** later sessions use `device_key` instead of the code (`mode:"trusted"`). The TV can forget all
  senders (Menu key); a sender that is no longer trusted is told to pair again.
- **Media:** `session_key = HKDF(key, salt=ns||nr, info="AirScreen-session")`; payload = AES-256-GCM(plaintext),
  nonce = 8 zero bytes || seq(u32), AAD = the 24-byte header (length = ciphertext length incl. 16-byte tag).
- Test vectors: `shared/test-data/crypto_vectors.json` (checked by Python and Kotlin unit tests).

## Capabilities (`caps`, TV -> sender) and automatic quality
`{"video":{"modes":[{"w","h","fps"}...]},"display":{"w","h","refresh"},"net":{"type","link_mbps"},"audio":{...}}`.
The sender picks the highest resolution every link in the chain supports (never upscaling), then the highest fps >= 30,
and a bitrate from pixels x fps, capped at 40% of the reported link speed. Manual `--size/--fps/--bitrate` override it.

## Receiver rules
Reject on bad magic/version/type/length, sequence gap, failed authentication or failed GCM tag. Never feed the decoder
before the first keyframe. Malformed data must never crash the receiver: drop the session and return to waiting.

## Sender rules
Bounded queue; when the network is behind, drop video and resume at the next keyframe (audio is kept). Keyframe at least once per second.
