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


# ---- approval pairing (v2.1): short pair key to find the TV, P-256 ECDH for the key exchange, 4-digit number to compare ----
from cryptography.hazmat.primitives import serialization as _ser
from cryptography.hazmat.primitives.asymmetric import ec

KEY_LENGTH = 6  # shown on the TV; it only proves the request comes from someone who can see the screen


def new_pair_key() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(KEY_LENGTH))


def format_key(key: str) -> str:
    return f"{key[:3]}-{key[3:]}"


def normalize_key(text: str) -> str:
    cleaned = "".join(ch for ch in text.upper() if ch not in " -")
    if len(cleaned) != KEY_LENGTH or any(c not in CODE_ALPHABET for c in cleaned):
        raise ValueError("The pair key has 6 letters or digits, shown on your TV as XXX-XXX")
    return cleaned


def new_keypair():
    """P-256 ephemeral key pair; the public key is the 65-byte uncompressed point (works on every Android version)."""
    priv = ec.generate_private_key(ec.SECP256R1())
    return priv, priv.public_key().public_bytes(_ser.Encoding.X962, _ser.PublicFormat.UncompressedPoint)


def ecdh(priv, peer_public: bytes) -> bytes:
    pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), peer_public)   # rejects points not on the curve
    return priv.exchange(ec.ECDH(), pub)


def sas(shared: bytes, ns: bytes, nr: bytes) -> str:
    """4-digit number both screens show. A man in the middle ends up with two different shared secrets, so the numbers differ."""
    h = hmac.new(shared, b"AirScreen-verify" + ns + nr, hashlib.sha256).digest()
    return f"{int.from_bytes(h[:4], 'big') % 10000:04d}"
