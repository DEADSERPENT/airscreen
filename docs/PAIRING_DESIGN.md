# Pairing design (security level 2)

## Problems fixed
1. **Grindable 4-digit number.** The sender revealed its ECDH key after the TV's, with nothing binding it first. A man in the
   middle could generate keys until both sides showed the same 4 digits (about 10^4 tries, seconds), then relay everything.
2. **Pair key sent in the clear** in `AUTH_PROOF` before the channel was authenticated.
3. A failed proof deleted a paired key (fixed earlier); one global lockout let one host lock everyone out; the AES-GCM nonce
   (u32 sequence) could wrap; device keys were stored in plaintext.

## Handshake (new fields in bold; header version stays 2)
```
S -> R  AUTH_REQUEST   {device_id, name, ns, **commit**}
          commit = SHA256("AirScreen-commit" || ns || device_id || pub_S)      (sender's ephemeral P-256 key chosen up front)
R -> S  AUTH_CHALLENGE {nr, receiver_id, name, trusted, caps, rpub, **sec: 2**}
S -> R  AUTH_PROOF     {mode:"request", pub: pub_S, **kp**}                      (reveal)
          kp = HMAC(shared, "AirScreen-pairkey" || ns || nr || pair_key || pub_S || rpub)     shared = ECDH(pub_S, rpub)
R:      checks SHA256("AirScreen-commit" || ns || device_id || pub_S) == commit, recomputes kp from its pair key,
        then shows the 4-digit number (HMAC(shared, "AirScreen-verify" || ns || nr)) and asks the person to Allow.
```
* **Why it stops grinding:** the sender commits to `pub_S` before the TV reveals `rpub`. An attacker relaying to the TV must
  therefore fix the key it shows the TV before it knows the TV's key, and must fix the key it shows the PC before it sees the
  PC's key. Neither number can be steered afterwards; each attempt succeeds with probability 1/10,000 and needs a person
  to press Allow, so repeated attempts are visible on the TV.
* **Pair key:** never sent. A passive listener learns nothing (the proof is keyed by the ECDH secret). It still only proves the
  requester can see the TV; approval + number are the real checks.
* **Downgrade:** a TV without `sec: 2` is refused for pairing by the sender ("update the TV app"); a TV refuses any pairing
  request without `commit`. Trusted-device reconnects are unchanged and keep working with older apps.

## Other changes
* Per-host lockout: 5 wrong keys lock that IP for 60 s (doubling to 15 min). The key rotates only after 3 lockouts in 10 min
  (distributed guessing), so one host cannot keep resetting the key.
* Handshake deadline on the TV (done) and session ends before the 32-bit sequence can wrap (nonce never reused).
* Device keys at rest: Windows DPAPI (per user), Android Keystore AES-GCM; old plaintext entries are migrated on first read.

## Not covered
Physical access to the TV or PC, malware on either, and a person approving without comparing the numbers.
