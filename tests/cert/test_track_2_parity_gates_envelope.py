"""Track 2 parity — confidence + HiTL + manifest provenance recording
(Plan 7 Phase 1 sub-task 3).

Exercises RC-003 (confidence), RC-004 (HiTL chain inspection), and
MF-001 / MF-002 (manifest provenance pass/fail recording) via
`make_app(...)` TestClient.

Important framing per `docs/open-core-extraction-plan.md`: the gateway's
`check_confidence` / `check_hitl` are *envelope-time cert-property
verifiers*; they do **not** replace OpenCastor's runtime
`ConfidenceGateManager` / `HiTLGateManager` orchestration. The two layers
complement each other. This test exercises only the cert-side via
make_app(...). Production wiring of make_app(...) into castor/api.py
(Phase 2) is where the cert-side runs alongside OpenCastor's runtime.

Fixture pattern mirrors gateway's
`tests/cert/test_rc_003_004_receiver_wiring.py` and
`tests/cert/test_mf_001_manifest_accept.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from robot_md_gateway.cert import report as cert_report
from robot_md_gateway.cert.gates import ConfidencePolicy, HiTLPolicy
from robot_md_gateway.cert.policy import ToolAllowlist
from robot_md_gateway.receiver import make_app

FIXTURES = Path(__file__).parent.parent / "fixtures" / "manifests"


class _FakeResolver:
    def __init__(self, mapping: dict[str, bytes]) -> None:
        self._mapping = mapping

    def resolve_public_key_pem(self, kid: str) -> bytes | None:
        return self._mapping.get(kid)


@pytest.fixture(autouse=True)
def _reset_cert_report():
    cert_report.reset()
    yield


def _client(*, confidence_policy=None, hitl_policy=None) -> TestClient:
    kid = (FIXTURES / "signing-key.kid").read_text().strip()
    pub = (FIXTURES / "signing-key.pub").read_bytes()
    app = make_app(
        resolver=_FakeResolver({kid: pub}),
        tool_allowlist=ToolAllowlist(
            allowed_tools=("mcp__robot__execute_capability", "mcp__robot__render"),
        ),
        bearer_tiers={"actuate-token": "actuate"},
        confidence_policy=confidence_policy,
        hitl_policy=hitl_policy,
    )
    return TestClient(app)


def _envelope(**overrides) -> dict:
    base = {
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
    base.update(overrides)
    return base


def test_rc_003_low_confidence_denied():
    client = _client(confidence_policy=ConfidencePolicy())
    response = client.post(
        "/v1/invoke",
        headers={"Authorization": "Bearer actuate-token"},
        json=_envelope(msg_id="msg-rc-003-low", payload={"inference_confidence": 0.5}),
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["deny"] == "confidence_threshold"


def test_rc_003_above_threshold_passes():
    client = _client(confidence_policy=ConfidencePolicy())
    response = client.post(
        "/v1/invoke",
        headers={"Authorization": "Bearer actuate-token"},
        json=_envelope(msg_id="msg-rc-003-good", payload={"inference_confidence": 0.95}),
    )
    assert response.status_code == 200, response.text


def test_rc_004_missing_chain_denied():
    client = _client(hitl_policy=HiTLPolicy())
    response = client.post(
        "/v1/invoke",
        headers={"Authorization": "Bearer actuate-token"},
        json=_envelope(msg_id="msg-rc-004-empty", delegation_chain=[]),
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["deny"] == "hitl_required"


def test_rc_004_with_chain_passes():
    client = _client(hitl_policy=HiTLPolicy())
    response = client.post(
        "/v1/invoke",
        headers={"Authorization": "Bearer actuate-token"},
        json=_envelope(msg_id="msg-rc-004-good"),
    )
    assert response.status_code == 200, response.text


def test_mf_001_signed_good_records_pass():
    client = _client()
    response = client.post(
        "/v1/invoke",
        headers={"Authorization": "Bearer actuate-token"},
        json=_envelope(msg_id="msg-mf-001-pass"),
    )
    assert response.status_code == 200
    serialized = cert_report.serialize(repo="opencastor-track-2", sha="HEAD")
    mf_001 = [p for p in serialized["properties"] if p["property_id"] == "MF-001"]
    assert len(mf_001) >= 1
    assert mf_001[0]["outcome"] == "pass"
    assert mf_001[0]["evidence"]["manifest_kid"]


def test_mf_002_tampered_manifest_records_fail():
    client = _client()
    response = client.post(
        "/v1/invoke",
        headers={"Authorization": "Bearer actuate-token"},
        json=_envelope(
            msg_id="msg-mf-002-fail",
            manifest_path=str(FIXTURES / "signed-tampered.md"),
        ),
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["deny"] == "manifest_provenance"
    serialized = cert_report.serialize(repo="opencastor-track-2", sha="HEAD")
    mf_002 = [p for p in serialized["properties"] if p["property_id"] == "MF-002"]
    assert len(mf_002) >= 1
    assert mf_002[0]["outcome"] == "fail"
