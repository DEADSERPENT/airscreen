# Known security work

- Pairing: the 4-digit number is compared by a person but is not yet protected by a commitment step, and the pair key is sent
  before the channel is authenticated. A commit-then-reveal design bound to the whole handshake transcript is planned.
- Fixed in 2.0.0: failed proofs no longer delete a paired key; the TV has one overall handshake deadline.
- Planned: per-IP pairing rate limits, nonce-exhaustion limit, DPAPI / Android Keystore protection of stored keys.
