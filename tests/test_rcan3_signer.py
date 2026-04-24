"""Tests for castor.rcan3.signer."""

from __future__ import annotations


def test_sign_round_trip(tmp_path):
    from castor.rcan3.identity import load_or_generate_identity
    from castor.rcan3.signer import CastorSigner

    ident = load_or_generate_identity(keydir=tmp_path)
    signer = CastorSigner(ident)
    body = {"msg_type": "register", "rrn": "RRN-000000000001", "data": {"a": 1}}

    signed = signer.sign(body)
    # rcan.sign_body produces 'sig', 'pq_signing_pub', 'pq_kid' at top level
    assert "sig" in signed
    assert "ml_dsa" in signed["sig"]
    assert "ed25519" in signed["sig"]
    assert signed["msg_type"] == "register"  # body fields preserved


def test_verify_returns_true_for_valid_signature(tmp_path):
    from castor.rcan3.identity import load_or_generate_identity
    from castor.rcan3.signer import CastorSigner

    ident = load_or_generate_identity(keydir=tmp_path)
    signer = CastorSigner(ident)
    body = {"msg_type": "register", "data": {"n": 42}}

    signed = signer.sign(body)
    assert signer.verify(signed) is True


def test_verify_false_for_tampered_body(tmp_path):
    from castor.rcan3.identity import load_or_generate_identity
    from castor.rcan3.signer import CastorSigner

    ident = load_or_generate_identity(keydir=tmp_path)
    signer = CastorSigner(ident)
    body = {"msg_type": "register", "data": {"n": 42}}

    signed = signer.sign(body)
    # Tamper with the body after signing
    signed_tampered = {**signed, "data": {"n": 99}}
    assert signer.verify(signed_tampered) is False
