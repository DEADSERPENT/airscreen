"""End-to-end handshake tests: the real sender handshake() against an in-process fake TV that mirrors StreamServer.kt."""
import hmac
import json
import socket
import threading

import pytest

from airscreen_sender.networking import crypto
from airscreen_sender.networking import protocol as P
from airscreen_sender.networking.tcp_sender import AuthError, PairingRequired, handshake
from airscreen_sender.networking.trust_store import TrustStore


def _recv(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    return buf


def _read(sock):
    h = P.parse_header(_recv(sock, P.HEADER_SIZE))
    return h, json.loads(_recv(sock, h.length) or b"{}")


def _send(sock, typ, seq, obj):
    sock.sendall(P.pack_message(typ, seq, 0, json.dumps(obj).encode()))


class FakeTV(threading.Thread):
    """Receiver side of the handshake. Flags let tests play an old TV, a TV that forgot us, or a man in the middle."""

    def __init__(self, sock, pair_key="K7X3QD", trusted_key=None, sec=2, approve=True, swap_pub=False):
        super().__init__(daemon=True)
        self.sock, self.pair_key, self.trusted_key, self.sec = sock, pair_key, trusted_key, sec
        self.approve, self.swap_pub = approve, swap_pub
        self.outcome, self.sas, self.device_key = None, None, None

    def run(self):
        try:
            self._serve()
        except Exception as e:  # pragma: no cover - surfaced through outcome
            self.outcome = f"crash: {e!r}"
        finally:
            self.sock.close()

    def _fail(self, reason):
        _send(self.sock, P.TYPE_AUTH_FAIL, 1, {"reason": reason})
        self.outcome = reason

    def _serve(self):
        _, req = _read(self.sock)
        ns, dev = bytes.fromhex(req["ns"]), req["device_id"]
        nr = crypto.new_nonce()
        priv, rpub = crypto.new_keypair()
        ch = {"nr": nr.hex(), "receiver_id": "tv1", "name": "Test TV", "trusted": self.trusted_key is not None,
              "caps": {}, "rpub": rpub.hex()}
        if self.sec:
            ch["sec"] = self.sec
        _send(self.sock, P.TYPE_AUTH_CHALLENGE, 0, ch)
        _, proof = _read(self.sock)
        if proof["mode"] == "trusted":
            if not self.trusted_key or not hmac.compare_digest(
                    bytes.fromhex(proof["proof"]), crypto.client_proof(self.trusted_key, ns, nr, dev)):
                return self._fail("authentication failed")
            _send(self.sock, P.TYPE_AUTH_OK, 1, {"proof": crypto.server_proof(self.trusted_key, ns, nr).hex()})
            self.outcome = "trusted"
            return
        # pairing request
        if not req.get("commit"):
            return self._fail("This PC app is too old for secure pairing.")
        pub = bytes.fromhex(proof["pub"])
        if not hmac.compare_digest(crypto.commit(ns, dev, pub), bytes.fromhex(req["commit"])):
            return self._fail("pairing commitment mismatch")
        shared = crypto.ecdh(priv, pub)
        expected = crypto.pair_key_proof(shared, ns, nr, self.pair_key, pub, rpub)
        if not hmac.compare_digest(expected, bytes.fromhex(proof.get("kp", ""))):
            return self._fail("wrong pair key")
        self.sas = crypto.sas(shared, ns, nr)
        if not self.approve:
            return self._fail("The TV did not approve this request")
        self.device_key = crypto.device_key(shared, ns, nr)
        _send(self.sock, P.TYPE_AUTH_OK, 1, {"proof": crypto.server_proof(shared, ns, nr).hex()})
        self.outcome = "paired"


def run(tmp_path, store=None, pair_key="K7X3QD", **tv_kwargs):
    store = store or TrustStore(tmp_path / "trust.json")
    a, b = socket.socketpair()
    a.settimeout(5)
    tv = FakeTV(b, **tv_kwargs)
    tv.start()
    seen = []
    try:
        result = handshake(a, store, pair_key, on_verify=seen.append)
        err = None
    except Exception as e:
        result, err = None, e
    finally:
        a.close()
    tv.join(3)
    return store, tv, seen, result, err


def test_new_pc_pairs_and_both_screens_show_the_same_number(tmp_path):
    store, tv, seen, result, err = run(tmp_path)
    assert err is None and tv.outcome == "paired"
    assert seen == [tv.sas]
    assert store.get_key("tv1") == tv.device_key


def test_wrong_pair_key_is_refused_and_nothing_is_stored(tmp_path):
    store, tv, _, _, err = run(tmp_path, pair_key="AAAAAA")
    assert isinstance(err, AuthError) and tv.outcome == "wrong pair key"
    assert store.get_key("tv1") is None


def test_pair_key_is_never_sent_in_clear(tmp_path, monkeypatch):
    sent = []
    real = socket.socket.sendall
    monkeypatch.setattr(socket.socket, "sendall", lambda self, data, *a: (sent.append(bytes(data)), real(self, data, *a))[1])
    run(tmp_path)
    assert sent and all(b"K7X3QD" not in d for d in sent)


def test_swapping_the_public_key_after_the_commitment_is_caught():
    """A man in the middle that shows the TV a different key than the PC committed to is rejected before any number is shown."""
    x, y = socket.socketpair()
    x.settimeout(5)
    tv = FakeTV(y)
    tv.start()
    priv, pub = crypto.new_keypair()
    ns = crypto.new_nonce()
    _send(x, P.TYPE_AUTH_REQUEST, 0, {"device_id": "pc1", "name": "x", "ns": ns.hex(), "commit": crypto.commit(ns, "pc1", pub).hex()})
    _, ch = _read(x)
    forged_priv, forged_pub = crypto.new_keypair()           # attacker substitutes its own key after seeing the TV's
    shared = crypto.ecdh(forged_priv, bytes.fromhex(ch["rpub"]))
    kp = crypto.pair_key_proof(shared, ns, bytes.fromhex(ch["nr"]), "K7X3QD", forged_pub, bytes.fromhex(ch["rpub"]))
    _send(x, P.TYPE_AUTH_PROOF, 1, {"mode": "request", "pub": forged_pub.hex(), "kp": kp.hex()})
    h, fail = _read(x)
    tv.join(3)
    assert h.type == P.TYPE_AUTH_FAIL and fail["reason"] == "pairing commitment mismatch" and tv.sas is None
    x.close()


def test_old_tv_without_secure_pairing_is_refused(tmp_path):
    _, tv, _, _, err = run(tmp_path, sec=0)
    assert isinstance(err, AuthError) and "too old" in str(err)


def test_trusted_reconnect_needs_no_key_and_no_prompt(tmp_path):
    store = TrustStore(tmp_path / "trust.json")
    key = crypto.new_nonce() * 2
    store.trust("tv1", "Test TV", key)
    _, tv, seen, _, err = run(tmp_path, store=store, pair_key=None, trusted_key=key)
    assert err is None and tv.outcome == "trusted" and seen == []


def test_tv_that_forgot_us_asks_to_pair_again_without_deleting_our_key(tmp_path):
    store = TrustStore(tmp_path / "trust.json")
    key = crypto.new_nonce() * 2
    store.trust("tv1", "Test TV", key)
    _, tv, _, _, err = run(tmp_path, store=store, pair_key=None, trusted_key=None)
    assert isinstance(err, PairingRequired)
    assert store.get_key("tv1") == key            # unauthenticated peers must not be able to wipe trust


def test_failed_proof_does_not_delete_the_stored_key(tmp_path):
    store = TrustStore(tmp_path / "trust.json")
    key = crypto.new_nonce() * 2
    store.trust("tv1", "Test TV", key)
    wrong = crypto.new_nonce() * 2
    _, tv, _, _, err = run(tmp_path, store=store, pair_key=None, trusted_key=wrong)
    assert isinstance(err, PairingRequired) and store.get_key("tv1") == key
