import json
import os

import pytest

from airscreen_sender.networking.trust_store import TrustStore

KEY = bytes(range(32))


def test_round_trip_and_not_plaintext_on_windows(tmp_path):
    s = TrustStore(tmp_path / "t.json")
    s.trust("tv1", "TV", KEY)
    assert TrustStore(tmp_path / "t.json").get_key("tv1") == KEY
    if os.name == "nt":
        assert KEY.hex() not in (tmp_path / "t.json").read_text()


def test_old_plaintext_entries_are_read_and_migrated(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps({"device_id": "abc", "device_name": "PC", "receivers": {"tv1": {"name": "TV", "key": KEY.hex()}}}))
    s = TrustStore(p)
    assert s.get_key("tv1") == KEY
    if os.name == "nt":
        assert KEY.hex() not in p.read_text()
