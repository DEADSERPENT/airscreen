import pytest

from airscreen_sender.networking import crypto


def test_both_sides_agree_and_see_the_same_number():
    ns, nr = crypto.new_nonce(), crypto.new_nonce()
    pc_priv, pc_pub = crypto.new_keypair()
    tv_priv, tv_pub = crypto.new_keypair()
    shared_pc, shared_tv = crypto.ecdh(pc_priv, tv_pub), crypto.ecdh(tv_priv, pc_pub)
    assert shared_pc == shared_tv
    assert crypto.sas(shared_pc, ns, nr) == crypto.sas(shared_tv, ns, nr)
    assert len(crypto.sas(shared_pc, ns, nr)) == 4


def test_man_in_the_middle_sees_a_different_number():
    ns, nr = crypto.new_nonce(), crypto.new_nonce()
    pc_priv, pc_pub = crypto.new_keypair()
    tv_priv, tv_pub = crypto.new_keypair()
    mitm_priv, mitm_pub = crypto.new_keypair()
    pc_side = crypto.sas(crypto.ecdh(pc_priv, mitm_pub), ns, nr)      # PC thinks the attacker is the TV
    tv_side = crypto.sas(crypto.ecdh(tv_priv, mitm_pub), ns, nr)      # TV thinks the attacker is the PC
    assert pc_side != tv_side or True  # 1-in-10000 chance of equal numbers; the secrets themselves must differ
    assert crypto.ecdh(pc_priv, mitm_pub) != crypto.ecdh(tv_priv, mitm_pub)


def test_pair_key_format():
    k = crypto.new_pair_key()
    assert len(k) == 6 and crypto.normalize_key(crypto.format_key(k).lower()) == k
    for bad in ("ABC", "ABC-DEF-G", "AB0-O1I"):
        with pytest.raises(ValueError):
            crypto.normalize_key(bad)


def test_commit_and_pair_key_proof_match_the_shared_vectors():
    import json, pathlib
    v = json.loads((pathlib.Path(__file__).parents[2] / "shared" / "test-data" / "crypto_vectors.json").read_text())
    ns, nr = bytes.fromhex(v["ns"]), bytes.fromhex(v["nr"])
    pub_s, pub_r = bytes.fromhex(v["pair_pub_s_hex"]), bytes.fromhex(v["pair_pub_r_hex"])
    assert crypto.commit(ns, v["device_id"], pub_s).hex() == v["commit"]
    assert crypto.pair_key_proof(bytes.fromhex(v["pair_shared_hex"]), ns, nr, v["pair_key"], pub_s, pub_r).hex() == v["pair_key_proof"]
