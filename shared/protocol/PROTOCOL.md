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
- **Pairing (first time), security level 2** (full rationale: `docs/PAIRING_DESIGN.md`): the TV shows a short **pair key**
  (`XXX-XXX`, single use, expires after 10 min). The PC commits to its ephemeral P-256 key in `AUTH_REQUEST`
  (`commit = SHA256("AirScreen-commit" || ns || device_id || pub_S)`), the TV's challenge carries `rpub` and `sec: 2`, then the PC
  reveals `AUTH_PROOF {mode:"request", pub, kp}` with `kp = HMAC(shared, "AirScreen-pairkey" || ns || nr || pair_key || pub_S || rpub)`.
  The TV checks the commitment and `kp` (the pair key is never sent), derives the 4-digit number
  `HMAC(shared, "AirScreen-verify" || ns || nr)` shown on both screens, and a person presses **Allow** on the TV.
  A TV that does not send `sec: 2` is refused for pairing; a TV rejects any pairing request without `commit`.
  Wrong tries lock the offending IP (5 tries, 60 s doubling to 15 min); the key rotates only after 3 lockouts in 10 min.
  The session ends before the 32-bit sequence number can wrap (GCM nonce is never reused).
- **Trusted devices:** after approval both sides store `device_key = HKDF(shared, ns||nr, "AirScreen-device-key")`.
  Later sessions use `AUTH_PROOF {mode:"trusted"}` with HMAC over fresh nonces; no key, no prompt.
- **Media:** `session_key = HKDF(key, salt=ns||nr, info="AirScreen-session")`; payload = AES-256-GCM(plaintext),
  nonce = 8 zero bytes || seq(u32), AAD = the 24-byte header (length = ciphertext length incl. 16-byte tag).
- Test vectors: `shared/test-data/crypto_vectors.json` (HMAC/HKDF/AES-GCM, checked by Python and Kotlin unit tests).

## Capabilities (`caps`, TV -> sender) and automatic quality
`{"video":{"modes":[{"w","h","fps"}...]},"display":{"w","h","refresh"},"net":{"type","link_mbps"},"audio":{...}}`.
The sender picks the highest resolution every link in the chain supports (never upscaling), then the highest fps >= 30,
and a bitrate from pixels x fps, capped at 40% of the reported link speed. Manual `--size/--fps/--bitrate` override it.

## Receiver rules
Reject on bad magic/version/type/length, sequence gap, failed authentication or failed GCM tag. Never feed the decoder
before the first keyframe. Malformed data must never crash the receiver: drop the session and return to waiting.

## Sender rules
Bounded queue; when the network is behind, drop video and resume at the next keyframe (audio is kept). Keyframe at least once per second.
