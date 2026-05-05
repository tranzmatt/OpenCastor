"""Track 2 (Gateway Authority) parity — full suite.

Plan 7 Phase 1 (`docs/open-core-extraction-plan.md`) closes the original
Plan 6 Task 13b placeholder: the cert-property surface lives in
`robot-md-gateway`, exercised here via `make_app(...)` end-to-end.

The 13 envelope-time cert properties (everything that fires through
`POST /v1/invoke`) are covered by the four sub-task test files:

| Sub-task | Property IDs | File |
|---|---|---|
| 1 — smoke | GW-002, GW-003 | test_track_2_parity_gateway_smoke.py |
| 2 — sign + replay + revoke | RC-001, RC-002, RR-001, RR-002 | test_track_2_parity_envelope_verification.py |
| 3 — gates + manifest | RC-003, RC-004, MF-001, MF-002 | test_track_2_parity_gates_envelope.py |
| 4 — safety + audit | SF-001, SF-002, EV-001 | test_track_2_parity_safety_audit.py |

Plus the additive manifest-provenance parity test
(`test_track_2_parity_manifest_provenance.py`) from Phase 0.

The 14th cert property — **GW-001 (device isolation)** — is verified at
the OS level (gateway-on-Bob owns `/dev/ttyACM0` exclusively, EACCES from
all other processes). It is *not* exercisable via TestClient because the
property is about OS process boundaries, not envelope content. GW-001's
verification is recorded at:
    `~/opencastor-ops/operations/2026-05-04-plan-6-phase-4-prep.md`
Task 18 — 10/10 EACCES verified on Bob 2026-05-04.

Track 2 NORMATIVE-conditional declaration:
    `~/opencastor-ops/operations/2026-05-04-track-2-normative.md`
"""

from __future__ import annotations

import base64
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from robot_md_gateway.cert import report as cert_report
from robot_md_gateway.cert.audit import AuditChain
from robot_md_gateway.cert.envelope import ReplayCache, canonical_json
from robot_md_gateway.cert.gates import ConfidencePolicy, HiTLPolicy
from robot_md_gateway.cert.policy import ToolAllowlist
from robot_md_gateway.cert.revocation import round_trip_register
from robot_md_gateway.cert.safety import SafetyMonitor
from robot_md_gateway.receiver import make_app

FIXTURES = Path(__file__).parent.parent / "fixtures" / "manifests"
ENV_KID = "envelope-signing-kid"


def test_robot_md_gateway_dependency_importable():
    """The Plan 7 integration target package must be importable from this venv."""
    import robot_md_gateway  # noqa: F401 — proves the dep installs cleanly
    assert robot_md_gateway.__version__ >= "0.4.0a1"


def test_gateway_cert_property_modules_present():
    """All Phase 0/1/2/4 cert-property modules ship with the gateway dep."""
    from robot_md_gateway.cert import (  # noqa: F401
        audit,
        envelope,
        gates,
        policy,
        revocation,
        safety,
    )


def test_track_2_parity_full_suite():
    """End-to-end: every envelope-time cert property fires through one make_app.

    Posts a curated sequence of envelopes through a fully-configured
    `make_app(...)` and asserts that all 13 envelope-time property IDs
    appear in `cert_report` afterward. GW-001 (device isolation) is
    verified separately at the OS layer — see module docstring.
    """
    cert_report.reset()

    # Build envelope-signing keypair + resolver that answers both
    # manifest kid and envelope kid.
    priv = Ed25519PrivateKey.generate()
    env_pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    manifest_kid = (FIXTURES / "signing-key.kid").read_text().strip()
    manifest_pub = (FIXTURES / "signing-key.pub").read_bytes()

    revoked_set: set[str] = set()

    class _Resolver:
        def resolve_public_key_pem(self, kid):
            if kid == manifest_kid:
                return manifest_pub
            if kid == ENV_KID:
                return env_pub_pem
            return None

    class _Revoker:
        def is_revoked(self, kid):
            return kid in revoked_set

    safety_monitor = SafetyMonitor(heartbeat_staleness_s=10.0)
    safety_monitor.on_heartbeat()  # start in READY

    app = make_app(
        resolver=_Resolver(),
        tool_allowlist=ToolAllowlist(
            allowed_tools=("mcp__robot__execute_capability", "mcp__robot__render"),
        ),
        bearer_tiers={"actuate-token": "actuate"},
        require_envelope_signature=True,
        replay_cache=ReplayCache(),
        confidence_policy=ConfidencePolicy(),
        hitl_policy=HiTLPolicy(),
        revocation_resolver=_Revoker(),
        safety_monitor=safety_monitor,
        audit_chain=AuditChain(),
    )
    client = TestClient(app)

    def signed(**overrides):
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
            "kid": ENV_KID, "alg": "Ed25519",
            "sig": base64.b64encode(sig).decode(),
        }
        return body

    headers = {"Authorization": "Bearer actuate-token"}

    # 1. Good envelope → MF-001, GW-002, GW-003, RC-001, RC-002 (first), RC-003, RC-004, RR-001 (allowed), EV-001
    r = client.post("/v1/invoke", headers=headers, json=signed(msg_id="m-good-1"))
    assert r.status_code == 200, r.text

    # 2. Replay same msg_id → RC-002 (fail)
    r = client.post("/v1/invoke", headers=headers, json=signed(msg_id="m-good-1"))
    assert r.status_code == 403
    assert r.json()["detail"]["deny"] == "replay"

    # 3. Tampered manifest → MF-002
    r = client.post("/v1/invoke", headers=headers, json=signed(
        msg_id="m-tampered-manifest",
        manifest_path=str(FIXTURES / "signed-tampered.md"),
    ))
    assert r.status_code == 403
    assert r.json()["detail"]["deny"] == "manifest_provenance"

    # 4. Disallowed tool → GW-003 (fail) — note: gateway records GW-002 on tool denial
    r = client.post("/v1/invoke", headers=headers, json=signed(
        msg_id="m-bad-tool", tool_name="mcp__robot__not_allowed",
    ))
    assert r.status_code == 403
    assert r.json()["detail"]["deny"] == "tool_allowlist"

    # 5. Low confidence → RC-003 (fail)
    r = client.post("/v1/invoke", headers=headers, json=signed(
        msg_id="m-low-conf", payload={"inference_confidence": 0.4},
    ))
    assert r.status_code == 403
    assert r.json()["detail"]["deny"] == "confidence_threshold"

    # 6. Empty delegation_chain → RC-004 (fail)
    r = client.post("/v1/invoke", headers=headers, json=signed(
        msg_id="m-no-chain", delegation_chain=[],
    ))
    assert r.status_code == 403
    assert r.json()["detail"]["deny"] == "hitl_required"

    # 7. Revoked kid → RR-001 (fail). The revocation cache from envelope #1
    # has a "not revoked" entry for ENV_KID; clear it so the resolver is
    # consulted again. RR-002 is exercised separately below — it only
    # fires on round_trip_register, not the receiver path.
    revoked_set.add(ENV_KID)
    app.state.revocation_cache._cache.clear()
    r = client.post("/v1/invoke", headers=headers, json=signed(msg_id="m-revoked"))
    assert r.status_code == 403
    assert r.json()["detail"]["deny"] == "revoked_key"
    revoked_set.discard(ENV_KID)

    # 8. Heartbeat staleness → SF-002 (fail)
    safety_monitor.last_heartbeat_at = time.monotonic() - 100.0
    safety_monitor._heartbeat_staleness_s = 0.05  # tighten threshold for the next tick
    r = client.post("/v1/invoke", headers=headers, json=signed(msg_id="m-stale"))
    assert r.status_code == 403
    assert r.json()["detail"]["deny"] == "safety_state"

    # 9. ESTOP trip → SF-001 (fail) — fresh heartbeat first to isolate the SF-001 cause.
    safety_monitor.on_heartbeat()
    safety_monitor._heartbeat_staleness_s = 10.0
    safety_monitor.on_estop_wire(tripped=True, msg_id="hw-trip-1")
    r = client.post("/v1/invoke", headers=headers, json=signed(msg_id="m-estop"))
    assert r.status_code == 403
    assert r.json()["detail"]["deny"] == "safety_state"

    # 10. RR-002 — round_trip_register is a separate API, not exercised
    # by the receiver. Use a stub registrar that echoes the registered
    # public key back for the resolve() round-trip.
    class _Registrar:
        def __init__(self):
            self._kids: dict[str, bytes] = {}

        def register(self, *, kid: str, public_key_pem: bytes) -> None:
            self._kids[kid] = public_key_pem

        def resolve(self, kid: str) -> bytes | None:
            return self._kids.get(kid)

    assert round_trip_register(
        registrar=_Registrar(),
        kid="opencastor-track-2-rr-002",
        public_key_pem=env_pub_pem,
    ) is True

    # 11. EV-001 — fires on AuditChain.export_signed, not the receiver path.
    audit_priv_pem = Ed25519PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    bundle = app.state.audit_chain.export_signed(
        signing_key_pem=audit_priv_pem, kid="opencastor-track-2-ev-001",
    )
    assert bundle["entry_count"] >= 1
    assert "signature" in bundle

    # All 13 envelope-time cert properties should now be present in cert_report.
    serialized = cert_report.serialize(repo="opencastor-track-2", sha="HEAD")
    seen = {p["property_id"] for p in serialized["properties"]}
    expected = {
        "MF-001", "MF-002",
        "GW-002", "GW-003",
        "RC-001", "RC-002", "RC-003", "RC-004",
        "RR-001", "RR-002",
        "SF-001", "SF-002",
        "EV-001",
    }
    missing = expected - seen
    assert not missing, (
        f"Track 2 full-suite missing property IDs: {sorted(missing)}. "
        f"Got: {sorted(seen)}"
    )
