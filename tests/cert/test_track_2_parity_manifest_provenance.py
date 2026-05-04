"""Track 2 parity — manifest provenance (Plan 7 Phase 0 Task 2).

Per `docs/open-core-extraction-plan.md`, manifest provenance is the
*additive* extraction module: OpenCastor has no signed-ROBOT.md verifier
today, so the extraction is "take the dependency + use it." Phase 0
exercises the gateway path against the same fixtures gateway uses;
Phase 1 wires the call site into OpenCastor's runtime.

Fixtures vendored from
    `robot-md-gateway/tests/fixtures/manifests/`
so this suite can run from the OpenCastor venv without a sibling
gateway checkout.
"""

from __future__ import annotations

from pathlib import Path

from robot_md_gateway.manifest_provenance import (
    ManifestProvenanceResult,
    verify_manifest,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "manifests"


class _Resolver:
    def __init__(self, mapping: dict[str, bytes]) -> None:
        self._m = mapping

    def resolve_public_key_pem(self, kid: str) -> bytes | None:
        return self._m.get(kid)


def _resolver_from_fixtures() -> _Resolver:
    kid = (FIXTURES / "signing-key.kid").read_text().strip()
    pub = (FIXTURES / "signing-key.pub").read_bytes()
    return _Resolver({kid: pub})


def test_manifest_provenance_accepts_signed_good() -> None:
    result = verify_manifest(FIXTURES / "signed-good.md", resolver=_resolver_from_fixtures())
    assert isinstance(result, ManifestProvenanceResult)
    assert result.accepted is True
    assert result.reason == "ok"
    assert result.kid is not None


def test_manifest_provenance_rejects_tampered() -> None:
    result = verify_manifest(FIXTURES / "signed-tampered.md", resolver=_resolver_from_fixtures())
    assert result.accepted is False
    assert "signature did not verify" in result.reason


def test_manifest_provenance_rejects_unknown_kid() -> None:
    empty = _Resolver({})
    result = verify_manifest(FIXTURES / "signed-good.md", resolver=empty)
    assert result.accepted is False
    assert "not registered with resolver" in result.reason
