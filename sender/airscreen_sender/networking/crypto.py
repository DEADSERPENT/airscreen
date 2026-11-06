"""Pairing + session crypto shared by the sender and the Python test receiver.

Design (see PROTOCOL.md "Security"):
  * First contact: user types the high-entropy pairing code shown on the TV (80 bits). Both sides
    prove knowledge of it with HMAC over fresh nonces, then derive a long-term device key.
  * Later sessions: the stored device key is used instead of the code ("trusted device").
  * Media is AES-256-GCM under a per-connection session key; the header is authenticated as AAD.
The code is never sent; a wrong code fails the HMAC and is rate-limited on the receiver.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
CODE_LENGTH = 16  # 16 * 5 bits = 80 bits


def new_pairing_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def format_code(code: str) -> str:
    return "-".join(code[i:i + 4] for i in range(0, len(code), 4))


def normalize_code(text: str) -> bytes:
    cleaned = "".join(ch for ch in text.upper() if ch not in " -")
    if len(cleaned) != CODE_LENGTH or any(c not in CODE_ALPHABET for c in cleaned):
        raise ValueError("pairing code must be 16 characters (letters/digits, shown as XXXX-XXXX-XXXX-XXXX)")
    return cleaned.encode()


def hkdf(ikm: bytes, salt: bytes, info: bytes, length: int = 32) -> bytes:
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    out, block, i = b"", b"", 1
    while len(out) < length:
        block = hmac.new(prk, block + info + bytes([i]), hashlib.sha256).digest()
        out += block
        i += 1
    return out[:length]


def new_nonce() -> bytes:
    return secrets.token_bytes(16)


def client_proof(key: bytes, ns: bytes, nr: bytes, device_id: str) -> bytes:
    return hmac.new(key, b"AirScreen-client" + ns + nr + device_id.encode(), hashlib.sha256).digest()


def server_proof(key: bytes, ns: bytes, nr: bytes) -> bytes:
    return hmac.new(key, b"AirScreen-server" + ns + nr, hashlib.sha256).digest()


def device_key(pairing_secret: bytes, ns: bytes, nr: bytes) -> bytes:
    return hkdf(pairing_secret, ns + nr, b"AirScreen-device-key")


def session_key(key: bytes, ns: bytes, nr: bytes) -> bytes:
    return hkdf(key, ns + nr, b"AirScreen-session")


def _nonce(seq: int) -> bytes:
    return b"\x00" * 8 + (seq & 0xFFFFFFFF).to_bytes(4, "big")


class MediaCipher:
    """AES-GCM with nonce = seq. A fresh session key per connection makes the nonce unique."""

    def __init__(self, key: bytes) -> None:
        self._aead = AESGCM(key)

    def seal(self, seq: int, plaintext: bytes, aad: bytes) -> bytes:
        return self._aead.encrypt(_nonce(seq), plaintext, aad)

    def open(self, seq: int, ciphertext: bytes, aad: bytes) -> bytes:
        return self._aead.decrypt(_nonce(seq), ciphertext, aad)


TAG_SIZE = 16
