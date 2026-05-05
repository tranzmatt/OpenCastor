"""Track 2 parity — envelope sig + replay + revocation (Plan 7 Phase 1 sub-task 2).

Exercises RC-001 (envelope signature), RC-002 (replay protection), and
RR-001 / RR-002 (key revocation) via `make_app(...)` TestClient.

Fixture pattern mirrors the gateway's
`tests/cert/test_phase_2_revocation_wiring.py` and
`tests/cert/test_rc_002_replay_protection.py` so any drift in the
make_app(...) signature or wiring surface is caught by both suites
simultaneously.

No source code in `castor/` is touched. Production wiring is Phase 2.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from robot_md_gateway.cert import report as cert_report
from robot_md_gateway.cert.envelope import canonical_json
from robot_md_gateway.cert.policy import ToolAllowlist
from robot_md_gateway.receiver import make_app

FIXTURES = Path(__file__).parent.parent / "fixtures" / "manifests"
ENV_KID = "envelope-signing-kid"


@pytest.fixture(autouse=True)
def _reset_cert_report():
    cert_report.reset()
    yield


@pytest.fixture
def env_keypair() -> tuple[Ed25519PrivateKey, bytes]:
    priv = Ed25519PrivateKey.generate()
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return priv, pub_pem


def _client(
    env_pub_pem: bytes,
    *,
    revocation_resolver=None,
    require_envelope_signature: bool = True,
) -> TestClient:
    manifest_kid = (FIXTURES / "signing-key.kid").read_text().strip()
    manifest_pub = (FIXTURES / "signing-key.pub").read_bytes()

    class _Resolver:
        def resolve_public_key_pem(self, kid):
            if kid == manifest_kid:
                return manifest_pub
            if kid == ENV_KID:
                return env_pub_pem
            return None

    app = make_app(
        resolver=_Resolver(),
        tool_allowlist=ToolAllowlist(
            allowed_tools=("mcp__robot__execute_capability", "mcp__robot__render"),
        ),
        bearer_tiers={"actuate-token": "actuate"},
        require_envelope_signature=require_envelope_signature,
        revocation_resolver=revocation_resolver,
    )
    return TestClient(app)


def _signed_envelope(priv: Ed25519PrivateKey, **overrides) -> dict:
    body = {
        "msg_id": overrides.pop("msg_id", "msg-default"),
        "type": "INVOKE",
        "ruri": "rcan://opencastor.local/robot/bob/00000003",
        "scope": "MANIPULATE",
        "tool_name": "mcp__robot__execute_capability",
        "tool_args": {},
        "manifest_path": str(FIXTURES / "signed-good.md"),
        "payload": {"inference_confidence": 0.95},
        "delegation_chain": [
            {"scope": "MANIPULATE", "human_subject": "operator@opencastor.local"},
        ],
    }
    body.update(overrides)
    sig = priv.sign(canonical_json(body))
    body["envelope_signature"] = {
        "kid": ENV_KID,
        "alg": "Ed25519",
        "sig": base64.b64encode(sig).decode(),
    }
    return body


def test_rc_001_signed_envelope_accepted(env_keypair):
    priv, pub_pem = env_keypair
    client = _client(pub_pem)
    response = client.post(
        "/v1/invoke",
        headers={"Authorization": "Bearer actuate-token"},
        json=_signed_envelope(priv, msg_id="msg-rc-001-good"),
    )
    assert response.status_code == 200, response.text


def test_rc_001_tampered_envelope_rejected(env_keypair):
    priv, pub_pem = env_keypair
    client = _client(pub_pem)
    env = _signed_envelope(priv, msg_id="msg-rc-001-tamper")
    # Mutate after signing — signature no longer matches canonicalized body.
    env["scope"] = "READ"
    response = client.post(
        "/v1/invoke",
        headers={"Authorization": "Bearer actuate-token"},
        json=env,
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["deny"] == "envelope_signature"


def test_rc_002_replay_rejected(env_keypair):
    priv, pub_pem = env_keypair
    client = _client(pub_pem)
    env = _signed_envelope(priv, msg_id="msg-rc-002-replay")
    first = client.post(
        "/v1/invoke",
        headers={"Authorization": "Bearer actuate-token"},
        json=env,
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/v1/invoke",
        headers={"Authorization": "Bearer actuate-token"},
        json=env,
    )
    assert second.status_code == 403, second.text
    assert second.json()["detail"]["deny"] == "replay"


def test_rr_001_revoked_kid_denied(env_keypair):
    priv, pub_pem = env_keypair

    class _Revoker:
        def is_revoked(self, kid):
            return kid == ENV_KID

    client = _client(pub_pem, revocation_resolver=_Revoker())
    response = client.post(
        "/v1/invoke",
        headers={"Authorization": "Bearer actuate-token"},
        json=_signed_envelope(priv, msg_id="msg-rr-001-revoked"),
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["deny"] == "revoked_key"
    assert ENV_KID in response.json()["detail"]["reason"]


def test_rr_002_unrevoked_kid_records_pass(env_keypair):
    priv, pub_pem = env_keypair

    class _NotRevoker:
        def is_revoked(self, kid):
            return False

    client = _client(pub_pem, revocation_resolver=_NotRevoker())
    response = client.post(
        "/v1/invoke",
        headers={"Authorization": "Bearer actuate-token"},
        json=_signed_envelope(priv, msg_id="msg-rr-002-pass"),
    )
    assert response.status_code == 200, response.text
    serialized = cert_report.serialize(repo="opencastor-track-2", sha="HEAD")
    rr_001 = [p for p in serialized["properties"] if p["property_id"] == "RR-001"]
    assert len(rr_001) == 1
    assert rr_001[0]["evidence"]["outcome"] == "allowed (not revoked)"
