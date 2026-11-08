# Security status

Done in 2.0.x (see `docs/PAIRING_DESIGN.md`):
- Pairing: commit-then-reveal key exchange (the 4-digit number can no longer be ground by a man in the middle), pair key never sent,
  TV refuses pairing from apps without it, failed proofs never delete a paired key, overall handshake deadline on the TV.
- Per-IP pairing lockout; session ends before the GCM nonce counter can wrap.
- Device keys at rest: Windows DPAPI, Android Keystore (old plaintext entries migrate automatically).
- Handshake covered by automated tests (`sender/tests/test_handshake.py`) and shared test vectors.

Still open:
- The 4-digit number is a human check (1 in 10,000 per attempt by design); someone must compare it before pressing Allow.
- No transport-level protection for the unauthenticated challenge fields (`caps`) before pairing completes.
- Not yet validated on real hardware after this change (the TV was offline); no independent security review.
