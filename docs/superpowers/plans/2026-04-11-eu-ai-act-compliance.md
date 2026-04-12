# EU AI Act Compliance Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 9 compliance gaps identified in the EU AI Act compliance study before the August 2, 2026 enforcement deadline.

**Architecture:** Four Critical gaps (Art. 16 strict mode, Art. 50 watermark enforcement, Art. 49 EU register command, Art. 72 post-market monitoring) ship as new modules and conformance checks. Five Warn gaps (Art. 10 model provenance, Art. 11 Annex IV table, Art. 13 IFU, Art. 17 QMS declaration, §22 spec page) extend existing `fria.py` and `conformance.py`. All changes follow the existing `ConformanceResult` + `build_fria_document` patterns.

**Tech Stack:** Python 3.10+, dataclasses, argparse (existing patterns), pytest, ruff, JSON/JSONL for incident storage.

---

## File Map

| File | Change |
|---|---|
| `castor/conformance.py` | Add `annex_iii_strict` param; new checks `rcan_v22.watermark_enforced`, `rcan_v22.qms_declaration`; strict-mode promotion of Art. 16 checks |
| `castor/fria.py` | Add `model_provenance`, `annex_iv_coverage`, `qms_reference` to `build_fria_document`; `annex_iii_strict` to `check_fria_prerequisite` |
| `castor/eu_register.py` | New — EU AI Act database submission package generator |
| `castor/incidents.py` | New — post-market monitoring incident log (Art. 72) |
| `castor/cli.py` | New commands: `castor eu-register`, `castor incidents`; `--annex-iii-strict` on `castor fria generate` |
| `tests/test_conformance.py` | New tests for `rcan_v22.watermark_enforced`, `rcan_v22.qms_declaration`, strict-mode Art. 16 |
| `tests/test_fria.py` | New tests for `model_provenance`, `annex_iv_coverage`, `qms_reference` |
| `tests/test_eu_register.py` | New — EU register module tests |
| `tests/test_incidents.py` | New — incident log tests |
| `tests/test_cli.py` | New tests for `castor eu-register`, `castor incidents`, `--annex-iii-strict` |

---

## Task 1: Art. 16 Annex III Strict Mode

Elevate SBOM, firmware manifest, and authority handler conformance checks from warn to fail when the system is declared as Annex III high-risk. Adds `annex_iii_strict: bool` to `ConformanceChecker` and `check_fria_prerequisite`. Adds `--annex-iii-strict` CLI flag to `castor fria generate`.

**Files:**
- Modify: `castor/conformance.py` — `ConformanceChecker.__init__`, `_v21_firmware_manifest`, `_v21_sbom_attestation`, `_v21_authority_handler`, `run_all`
- Modify: `castor/fria.py` — `check_fria_prerequisite`
- Modify: `castor/cli.py` — `cmd_fria_generate`, fria generate subparser
- Test: `tests/test_conformance.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_conformance.py`:

```python
class TestAnnexIIIStrictMode:
    """Art. 16 checks promote from warn to fail in strict mode."""

    base_config = {
        "rcan_version": "2.2",
        "metadata": {"rrn": "RRN-000000000001"},
        "reactive": {"min_obstacle_m": 0.3},
        "agent": {"provider": "google", "model": "gemini-2.5-flash"},
    }

    def test_sbom_warn_in_default_mode(self):
        checker = ConformanceChecker(self.base_config)
        results = checker.run_category("rcan_v21")
        sbom = next(r for r in results if r.check_id == "rcan_v21.sbom_attestation")
        assert sbom.status == "warn"

    def test_sbom_fail_in_strict_mode(self):
        checker = ConformanceChecker(self.base_config, annex_iii_strict=True)
        results = checker.run_category("rcan_v21")
        sbom = next(r for r in results if r.check_id == "rcan_v21.sbom_attestation")
        assert sbom.status == "fail"

    def test_firmware_fail_in_strict_mode(self):
        checker = ConformanceChecker(self.base_config, annex_iii_strict=True)
        results = checker.run_category("rcan_v21")
        fw = next(r for r in results if r.check_id == "rcan_v21.firmware_manifest")
        assert fw.status == "fail"

    def test_authority_fail_in_strict_mode(self):
        checker = ConformanceChecker(self.base_config, annex_iii_strict=True)
        results = checker.run_category("rcan_v21")
        auth = next(r for r in results if r.check_id == "rcan_v21.authority_handler")
        # warn → fail; ImportError → fail either way
        assert auth.status == "fail"

    def test_strict_mode_does_not_affect_non_art16_checks(self):
        """Strict mode only affects Art. 16 checks, not other categories."""
        checker_default = ConformanceChecker(self.base_config)
        checker_strict = ConformanceChecker(self.base_config, annex_iii_strict=True)
        default_safety = checker_default.run_category("safety")
        strict_safety = checker_strict.run_category("safety")
        assert [r.status for r in default_safety] == [r.status for r in strict_safety]

    def test_check_fria_prerequisite_strict_blocks_on_art16(self):
        from castor.fria import check_fria_prerequisite
        passed, blocking = check_fria_prerequisite(self.base_config, annex_iii_strict=True)
        blocking_ids = [r.check_id for r in blocking]
        assert "rcan_v21.sbom_attestation" in blocking_ids
        assert not passed
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /home/craigm26/OpenCastor
pytest tests/test_conformance.py::TestAnnexIIIStrictMode -v
```

Expected: FAIL — `ConformanceChecker.__init__` does not accept `annex_iii_strict`.

- [ ] **Step 3: Add `annex_iii_strict` to `ConformanceChecker.__init__`**

In `castor/conformance.py`, update `__init__`:

```python
def __init__(self, config: dict, config_path: str | None = None, annex_iii_strict: bool = False) -> None:
    self._cfg = config or {}
    self._config_path = config_path
    self._annex_iii_strict = annex_iii_strict
```

- [ ] **Step 4: Promote Art. 16 warn results to fail in strict mode**

In `castor/conformance.py`, update `_v21_sbom_attestation` — replace the final return (no SBOM found) and the unsigned-SBOM return:

The file currently has two warn returns in `_v21_sbom_attestation` (lines ~1970-1984). Replace both final warn returns with a helper call:

```python
def _v21_sbom_attestation(self) -> ConformanceResult:
    cid = "rcan_v21.sbom_attestation"
    import os

    sbom_paths = [
        "/run/opencastor/rcan-sbom.json",
        "/tmp/opencastor-rcan-sbom.json",
    ]
    for p in sbom_paths:
        if os.path.exists(p):
            try:
                import json as _json

                d = _json.loads(open(p).read())
                rcan = d.get("x-rcan", {})
                has_countersig = bool(rcan.get("rrf_countersig"))
                if has_countersig:
                    return ConformanceResult(
                        check_id=cid,
                        category="rcan_v21",
                        status="pass",
                        detail=f"SBOM found at {p} with RRF countersignature",
                    )
                return ConformanceResult(
                    check_id=cid,
                    category="rcan_v21",
                    status="fail" if self._annex_iii_strict else "warn",
                    detail=f"SBOM found at {p} but not yet RRF-countersigned",
                    fix="Run: castor sbom publish --token <rrf-token>",
                )
            except Exception:
                pass
    return ConformanceResult(
        check_id=cid,
        category="rcan_v21",
        status="fail" if self._annex_iii_strict else "warn",
        detail="No SBOM found (required for EU AI Act Art. 16(a) in production)",
        fix="Run: castor sbom generate && castor sbom publish --token <rrf-token>",
    )
```

Apply the same `"fail" if self._annex_iii_strict else "warn"` pattern to `_v21_firmware_manifest` (both its warn returns) and `_v21_authority_handler` (both its warn returns). The `_v21_authority_handler` ImportError path already returns `fail` — leave it as-is.

- [ ] **Step 5: Update `check_fria_prerequisite` in `castor/fria.py`**

```python
def check_fria_prerequisite(
    config: dict,
    annex_iii_strict: bool = False,
) -> tuple[bool, list[ConformanceResult]]:
    """Run conformance checks and return (gate_passed, blocking_results).

    Gate passes when conformance score >= 80 and there are zero safety.* failures.
    When annex_iii_strict=True, Art. 16 checks (SBOM, firmware, authority) are
    promoted from warn to fail, raising the bar for Annex III high-risk systems.
    """
    checker = ConformanceChecker(config, annex_iii_strict=annex_iii_strict)
    results = checker.run_all()
    summary = checker.summary(results)

    safety_failures = [r for r in results if r.category == "safety" and r.status == "fail"]
    score_ok = summary["score"] >= CONFORMANCE_SCORE_MIN
    gate_passed = score_ok and len(safety_failures) == 0

    if not gate_passed:
        blocking = [r for r in results if r.status == "fail"] if not score_ok else safety_failures
    else:
        blocking = []

    return gate_passed, blocking
```

- [ ] **Step 6: Add `--annex-iii-strict` to `cmd_fria_generate` in `castor/cli.py`**

In `cmd_fria_generate`, after the existing `prerequisite_waived` logic, add:

```python
annex_iii_strict = getattr(args, "annex_iii_strict", False)
```

And update the `check_fria_prerequisite` call:

```python
gate_passed, blocking = check_fria_prerequisite(config, annex_iii_strict=annex_iii_strict)
```

Also update the call inside `build_fria_document` — since `build_fria_document` calls `ConformanceChecker` internally, pass it through:

```python
doc = build_fria_document(
    config=config,
    annex_iii_basis=annex_iii,
    intended_use=intended_use,
    memory_path=memory_path,
    prerequisite_waived=prerequisite_waived,
    benchmark_path=getattr(args, "benchmark_path", None),
    annex_iii_strict=annex_iii_strict,
)
```

Then update `build_fria_document` signature in `castor/fria.py` to accept and pass through `annex_iii_strict`:

```python
def build_fria_document(
    config: dict,
    annex_iii_basis: str,
    intended_use: str,
    memory_path: str | None = None,
    prerequisite_waived: bool = False,
    benchmark_path: str | None = None,
    annex_iii_strict: bool = False,
) -> dict:
```

And update the `ConformanceChecker` instantiation inside `build_fria_document`:

```python
checker = ConformanceChecker(config, annex_iii_strict=annex_iii_strict)
```

Add the CLI argument to the fria generate subparser (in the section around line 6840 in cli.py, where other fria args are added):

```python
p_fria_gen.add_argument(
    "--annex-iii-strict",
    dest="annex_iii_strict",
    action="store_true",
    default=False,
    help=(
        "Promote Art. 16 conformance checks (SBOM, firmware manifest, authority handler) "
        "from warn to fail. Required for Annex III high-risk system deployments."
    ),
)
```

- [ ] **Step 7: Run the failing tests again**

```bash
pytest tests/test_conformance.py::TestAnnexIIIStrictMode -v
```

Expected: All 6 tests PASS.

- [ ] **Step 8: Write CLI tests**

Add to `tests/test_cli.py`:

```python
class TestFriaGenerateAnnexIIIStrict:
    def test_annex_iii_strict_flag_exists(self, tmp_path):
        """--annex-iii-strict is a valid flag (help exits 0)."""
        result = subprocess.run(
            ["python", "-m", "castor.cli", "fria", "generate", "--help"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "--annex-iii-strict" in result.stdout
```

- [ ] **Step 9: Run all conformance and CLI tests**

```bash
pytest tests/test_conformance.py tests/test_cli.py tests/test_fria.py -v
```

Expected: All pass, no regressions.

- [ ] **Step 10: Commit**

```bash
git add castor/conformance.py castor/fria.py castor/cli.py tests/test_conformance.py tests/test_cli.py
git commit -m "feat: Art. 16 Annex III strict mode — promote SBOM/firmware/authority to fail for high-risk systems"
```

---

## Task 2: Art. 50 Watermark Enforcement Conformance Check

Add `rcan_v22.watermark_enforced` conformance check that fails when `safety.watermark_enforcement` is not enabled in config. This makes watermarking non-optional for AI-generated command payloads, closing the Art. 50 gap.

**Files:**
- Modify: `castor/conformance.py` — `_check_rcan_v21` + new `_v22_watermark_enforced` method
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_conformance.py`:

```python
class TestWatermarkEnforcedCheck:
    """rcan_v22.watermark_enforced — Art. 50 detectability."""

    def _checker(self, extra: dict | None = None):
        config = {
            "rcan_version": "2.2",
            "metadata": {"rrn": "RRN-000000000001"},
            "reactive": {"min_obstacle_m": 0.3},
            "agent": {"provider": "google", "model": "gemini-2.5-flash"},
        }
        if extra:
            config.update(extra)
        return ConformanceChecker(config)

    def test_fails_when_watermark_enforcement_absent(self):
        results = self._checker().run_category("rcan_v21")
        wm = next((r for r in results if r.check_id == "rcan_v22.watermark_enforced"), None)
        assert wm is not None
        assert wm.status == "fail"

    def test_fails_when_watermark_enforcement_false(self):
        results = self._checker({"safety": {"watermark_enforcement": False}}).run_category("rcan_v21")
        wm = next(r for r in results if r.check_id == "rcan_v22.watermark_enforced")
        assert wm.status == "fail"

    def test_passes_when_watermark_enforcement_true(self):
        results = self._checker({"safety": {"watermark_enforcement": True}}).run_category("rcan_v21")
        wm = next(r for r in results if r.check_id == "rcan_v22.watermark_enforced")
        assert wm.status == "pass"

    def test_check_id_and_category(self):
        results = self._checker().run_category("rcan_v21")
        wm = next(r for r in results if r.check_id == "rcan_v22.watermark_enforced")
        assert wm.category == "rcan_v22"

    def test_fix_message_present_when_failing(self):
        results = self._checker().run_category("rcan_v21")
        wm = next(r for r in results if r.check_id == "rcan_v22.watermark_enforced")
        assert wm.fix is not None
        assert "watermark_enforcement" in wm.fix
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_conformance.py::TestWatermarkEnforcedCheck -v
```

Expected: FAIL — `rcan_v22.watermark_enforced` check does not exist.

- [ ] **Step 3: Implement `_v22_watermark_enforced` in `castor/conformance.py`**

Add this method to `ConformanceChecker` (after `_v22_firmware_pq_sig`):

```python
def _v22_watermark_enforced(self) -> ConformanceResult:
    """RCAN v2.2 §16.5 — AI output watermarking MUST be enabled (EU AI Act Art. 50)."""
    cid = "rcan_v22.watermark_enforced"
    safety_cfg = self._cfg.get("safety", {}) or {}
    enabled = safety_cfg.get("watermark_enforcement", False)
    if enabled:
        return ConformanceResult(
            check_id=cid,
            category="rcan_v22",
            status="pass",
            detail="AI output watermarking enforcement enabled (Art. 50 compliant)",
        )
    return ConformanceResult(
        check_id=cid,
        category="rcan_v22",
        status="fail",
        detail=(
            "AI output watermark enforcement is disabled — EU AI Act Art. 50 requires "
            "AI-generated commands to be machine-detectable"
        ),
        fix=(
            "Add `safety:\\n  watermark_enforcement: true` to your RCAN config. "
            "Requires OPENCASTOR_WATERMARK_KEY env var (see castor/watermark.py)."
        ),
    )
```

Wire it into `_check_rcan_v21`:

```python
def _check_rcan_v21(self) -> list[ConformanceResult]:
    return [
        self._v21_firmware_manifest(),
        self._v21_sbom_attestation(),
        self._v21_authority_handler(),
        self._v21_audit_chain_retention(),
        self._v21_rcan_version(),
        self._v22_pq_signing_key(),
        self._v22_firmware_pq_sig(),
        self._v22_watermark_enforced(),
    ]
```

- [ ] **Step 4: Run the tests**

```bash
pytest tests/test_conformance.py::TestWatermarkEnforcedCheck -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Run full conformance test suite**

```bash
pytest tests/test_conformance.py -v
```

Expected: All pass, no regressions.

- [ ] **Step 6: Commit**

```bash
git add castor/conformance.py tests/test_conformance.py
git commit -m "feat: rcan_v22.watermark_enforced — Art. 50 watermark enforcement conformance check"
```

---

## Task 3: Art. 49 EU AI Act Database Submission Package

New `castor/eu_register.py` module that generates a structured EU AI Act database submission package from a signed FRIA artifact + RCAN config. New `castor eu-register` CLI command.

**Files:**
- Create: `castor/eu_register.py`
- Modify: `castor/cli.py` — `cmd_eu_register` + subparser
- Create: `tests/test_eu_register.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_eu_register.py`:

```python
"""Tests for castor.eu_register — EU AI Act Art. 49 database submission package."""
import json
import os
import tempfile
from pathlib import Path

import pytest

from castor.eu_register import build_submission_package, EU_AI_ACT_REGISTRATION_URL


SAMPLE_FRIA = {
    "schema": "rcan-fria-v1",
    "generated_at": "2026-04-11T09:00:00+00:00",
    "system": {
        "rrn": "RRN-000000000001",
        "rrn_uri": "rrn://org/robot/model/id",
        "robot_name": "test-robot",
        "opencastor_version": "2026.3.21.1",
        "rcan_version": "2.2",
        "agent_provider": "google",
        "agent_model": "gemini-2.5-flash",
    },
    "deployment": {
        "annex_iii_basis": "safety_component",
        "intended_use": "Indoor navigation assistance",
        "prerequisite_waived": False,
    },
    "conformance": {
        "score": 85,
        "pass": 20,
        "warn": 5,
        "fail": 0,
    },
    "human_oversight": {
        "hitl_configured": True,
        "confidence_gates_configured": True,
        "estop_configured": True,
    },
    "overall_pass": True,
}

SAMPLE_CONFIG = {
    "rcan_version": "2.2",
    "metadata": {
        "rrn": "RRN-000000000001",
        "robot_name": "test-robot",
    },
}


class TestBuildSubmissionPackage:
    def test_returns_dict_with_required_fields(self):
        pkg = build_submission_package(SAMPLE_FRIA, SAMPLE_CONFIG)
        assert "schema" in pkg
        assert "generated_at" in pkg
        assert "provider" in pkg
        assert "system" in pkg
        assert "annex_iii_basis" in pkg
        assert "conformity_status" in pkg
        assert "submission_instructions" in pkg

    def test_schema_value(self):
        pkg = build_submission_package(SAMPLE_FRIA, SAMPLE_CONFIG)
        assert pkg["schema"] == "rcan-eu-register-v1"

    def test_system_fields_populated_from_fria(self):
        pkg = build_submission_package(SAMPLE_FRIA, SAMPLE_CONFIG)
        assert pkg["system"]["rrn"] == "RRN-000000000001"
        assert pkg["system"]["robot_name"] == "test-robot"
        assert pkg["system"]["intended_use"] == "Indoor navigation assistance"

    def test_annex_iii_basis_from_fria(self):
        pkg = build_submission_package(SAMPLE_FRIA, SAMPLE_CONFIG)
        assert pkg["annex_iii_basis"] == "safety_component"

    def test_conformity_status_pass_when_fria_passes(self):
        pkg = build_submission_package(SAMPLE_FRIA, SAMPLE_CONFIG)
        assert pkg["conformity_status"]["fria_overall_pass"] is True
        assert pkg["conformity_status"]["conformance_score"] == 85

    def test_submission_instructions_contains_url(self):
        pkg = build_submission_package(SAMPLE_FRIA, SAMPLE_CONFIG)
        assert EU_AI_ACT_REGISTRATION_URL in pkg["submission_instructions"]

    def test_raises_on_wrong_fria_schema(self):
        bad_fria = {**SAMPLE_FRIA, "schema": "wrong-schema"}
        with pytest.raises(ValueError, match="rcan-fria-v1"):
            build_submission_package(bad_fria, SAMPLE_CONFIG)

    def test_json_serializable(self):
        pkg = build_submission_package(SAMPLE_FRIA, SAMPLE_CONFIG)
        serialized = json.dumps(pkg)
        assert len(serialized) > 0
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_eu_register.py -v
```

Expected: FAIL — `castor.eu_register` does not exist.

- [ ] **Step 3: Create `castor/eu_register.py`**

```python
"""castor.eu_register — EU AI Act Art. 49 database submission package generator.

Generates a structured submission package from a signed FRIA artifact + RCAN config.
The package contains all fields required for EU AI Act database registration.

Actual submission requires manual action at the EU AI Act registration portal —
this module generates the data package; it does not submit automatically.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

EU_AI_ACT_REGISTRATION_URL = "https://ec.europa.eu/digital-strategy/en/policies/european-ai-act"
SUBMISSION_SCHEMA_VERSION = "rcan-eu-register-v1"
FRIA_SCHEMA_REQUIRED = "rcan-fria-v1"


def build_submission_package(fria: dict, config: dict) -> dict[str, Any]:
    """Generate an EU AI Act Art. 49 database submission package.

    Args:
        fria:   Signed (or unsigned) FRIA document dict (schema must be 'rcan-fria-v1').
        config: Parsed RCAN config dict.

    Returns:
        Submission package dict ready for JSON serialization.

    Raises:
        ValueError: If ``fria["schema"]`` is not ``"rcan-fria-v1"``.
    """
    if fria.get("schema") != FRIA_SCHEMA_REQUIRED:
        raise ValueError(
            f"FRIA schema must be {FRIA_SCHEMA_REQUIRED!r}, got {fria.get('schema')!r}. "
            "Run `castor fria generate` to produce a valid FRIA."
        )

    meta = config.get("metadata", {}) or {}
    system_info = fria.get("system", {}) or {}
    deployment = fria.get("deployment", {}) or {}
    conformance = fria.get("conformance", {}) or {}
    human_oversight = fria.get("human_oversight", {}) or {}

    return {
        "schema": SUBMISSION_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fria_ref": {
            "generated_at": fria.get("generated_at", ""),
            "schema": fria.get("schema", ""),
        },
        "provider": {
            "name": meta.get("provider_name", ""),
            "contact": meta.get("provider_contact", ""),
            "rrn": system_info.get("rrn", meta.get("rrn", "")),
            "note": (
                "provider.name and provider.contact must be filled in manually. "
                "Add provider_name and provider_contact to your RCAN config metadata."
            ),
        },
        "system": {
            "rrn": system_info.get("rrn", ""),
            "rrn_uri": system_info.get("rrn_uri", ""),
            "robot_name": system_info.get("robot_name", ""),
            "opencastor_version": system_info.get("opencastor_version", ""),
            "rcan_version": system_info.get("rcan_version", ""),
            "agent_provider": system_info.get("agent_provider", ""),
            "agent_model": system_info.get("agent_model", ""),
            "intended_use": deployment.get("intended_use", ""),
        },
        "annex_iii_basis": deployment.get("annex_iii_basis", ""),
        "conformity_status": {
            "fria_overall_pass": fria.get("overall_pass", conformance.get("fail", 1) == 0),
            "conformance_score": conformance.get("score", 0),
            "hitl_configured": human_oversight.get("hitl_configured", False),
            "estop_configured": human_oversight.get("estop_configured", False),
            "fria_generated_at": fria.get("generated_at", ""),
        },
        "submission_instructions": (
            f"Register this system in the EU AI Act database at: {EU_AI_ACT_REGISTRATION_URL}\n"
            "Steps:\n"
            "1. Fill in provider.name and provider.contact in this package.\n"
            "2. Log in with your EU representative credentials.\n"
            "3. Create a new high-risk AI system registration.\n"
            "4. Upload this JSON package and your signed FRIA artifact.\n"
            "5. Await confirmation (typically 2-4 weeks).\n"
            "Deadline: August 2, 2026 for Annex III high-risk AI systems."
        ),
    }
```

- [ ] **Step 4: Run the tests**

```bash
pytest tests/test_eu_register.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Add `cmd_eu_register` to `castor/cli.py`**

Add after `cmd_fria` (around line 3967):

```python
def cmd_eu_register(args) -> None:
    """castor eu-register — generate EU AI Act Art. 49 database submission package."""
    import json as _json
    import sys
    from pathlib import Path

    import yaml

    from castor.eu_register import build_submission_package

    fria_path = getattr(args, "fria", None)
    if not fria_path or not Path(fria_path).exists():
        print(f"Error: FRIA file not found: {fria_path!r}", file=sys.stderr)
        print("Run `castor fria generate` first.", file=sys.stderr)
        raise SystemExit(1)

    config_path = getattr(args, "config", None) or "robot.rcan.yaml"
    if not Path(config_path).exists():
        print(f"Error: config file not found: {config_path!r}", file=sys.stderr)
        raise SystemExit(1)

    with open(fria_path) as f:
        fria = _json.load(f)
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    try:
        package = build_submission_package(fria, config)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)

    output = getattr(args, "output", None)
    if output:
        with open(output, "w") as f:
            _json.dump(package, f, indent=2, default=str)
        print(f"Submission package written to: {output}")
    else:
        print(_json.dumps(package, indent=2, default=str))

    print("\n" + package["submission_instructions"], file=sys.stderr)
```

Add the subparser in the CLI setup section (near the `fria` subparser around line 6838):

```python
# ── eu-register ───────────────────────────────────────────────────────────────
p_eu_register = sub.add_parser(
    "eu-register",
    help="Generate EU AI Act Art. 49 database submission package from FRIA artifact",
)
p_eu_register.add_argument("fria", metavar="FRIA_FILE", help="Signed FRIA JSON artifact")
p_eu_register.add_argument(
    "--config", metavar="FILE", default="robot.rcan.yaml", help="RCAN config file"
)
p_eu_register.add_argument(
    "--output", metavar="FILE", help="Output path (default: print to stdout)"
)
p_eu_register.set_defaults(func=cmd_eu_register)
```

- [ ] **Step 6: Add CLI tests**

Add to `tests/test_cli.py`:

```python
class TestEuRegisterCli:
    def test_help_exits_0(self):
        result = subprocess.run(
            ["python", "-m", "castor.cli", "eu-register", "--help"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "FRIA" in result.stdout

    def test_missing_fria_exits_1(self, tmp_path):
        config = tmp_path / "robot.rcan.yaml"
        config.write_text("rcan_version: '2.2'\nmetadata:\n  rrn: RRN-000000000001\n")
        result = subprocess.run(
            ["python", "-m", "castor.cli", "eu-register", "nonexistent.json",
             "--config", str(config)],
            capture_output=True, text=True
        )
        assert result.returncode == 1
```

- [ ] **Step 7: Run all tests**

```bash
pytest tests/test_eu_register.py tests/test_cli.py -v
```

Expected: All pass.

- [ ] **Step 8: Commit**

```bash
git add castor/eu_register.py castor/cli.py tests/test_eu_register.py tests/test_cli.py
git commit -m "feat: castor eu-register — Art. 49 EU AI Act database submission package generator"
```

---

## Task 4: Art. 72 Post-Market Monitoring Foundation

New `castor/incidents.py` module providing an incident log (JSONL-based) and report generation per Art. 72. New `castor incidents` CLI command with `record`, `list`, and `report` subcommands.

**Files:**
- Create: `castor/incidents.py`
- Modify: `castor/cli.py`
- Create: `tests/test_incidents.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_incidents.py`:

```python
"""Tests for castor.incidents — Art. 72 post-market monitoring."""
import json
import tempfile
from pathlib import Path

import pytest

from castor.incidents import (
    IncidentLog,
    IncidentSeverity,
    generate_report,
    INCIDENT_SCHEMA_VERSION,
)


class TestIncidentLog:
    def test_record_creates_entry(self, tmp_path):
        log = IncidentLog(tmp_path / "incidents.jsonl")
        log.record(
            severity=IncidentSeverity.OTHER,
            category="test_category",
            description="Test incident",
            system_state={"driver": "simulation"},
        )
        entries = log.list_incidents()
        assert len(entries) == 1
        assert entries[0]["severity"] == "other"
        assert entries[0]["category"] == "test_category"
        assert entries[0]["description"] == "Test incident"

    def test_record_assigns_uuid_id(self, tmp_path):
        log = IncidentLog(tmp_path / "incidents.jsonl")
        log.record(IncidentSeverity.OTHER, "cat", "desc", {})
        entries = log.list_incidents()
        assert len(entries[0]["id"]) == 36  # UUID4 format

    def test_record_assigns_timestamp(self, tmp_path):
        log = IncidentLog(tmp_path / "incidents.jsonl")
        log.record(IncidentSeverity.OTHER, "cat", "desc", {})
        entries = log.list_incidents()
        assert "T" in entries[0]["timestamp"]  # ISO 8601

    def test_life_health_severity(self, tmp_path):
        log = IncidentLog(tmp_path / "incidents.jsonl")
        log.record(IncidentSeverity.LIFE_HEALTH, "estop", "ESTOP triggered", {})
        entries = log.list_incidents()
        assert entries[0]["severity"] == "life_health"

    def test_persists_across_instances(self, tmp_path):
        path = tmp_path / "incidents.jsonl"
        IncidentLog(path).record(IncidentSeverity.OTHER, "cat", "desc", {})
        IncidentLog(path).record(IncidentSeverity.OTHER, "cat2", "desc2", {})
        entries = IncidentLog(path).list_incidents()
        assert len(entries) == 2

    def test_empty_log_returns_empty_list(self, tmp_path):
        log = IncidentLog(tmp_path / "incidents.jsonl")
        assert log.list_incidents() == []


class TestGenerateReport:
    def test_report_schema_and_fields(self, tmp_path):
        log = IncidentLog(tmp_path / "incidents.jsonl")
        log.record(IncidentSeverity.OTHER, "cat", "Test incident", {"rrn": "RRN-1"})
        report = generate_report(log)
        assert report["schema"] == INCIDENT_SCHEMA_VERSION
        assert "generated_at" in report
        assert "total_incidents" in report
        assert "incidents_by_severity" in report
        assert "incidents" in report

    def test_report_counts_by_severity(self, tmp_path):
        log = IncidentLog(tmp_path / "incidents.jsonl")
        log.record(IncidentSeverity.LIFE_HEALTH, "estop", "Critical", {})
        log.record(IncidentSeverity.OTHER, "config", "Minor", {})
        report = generate_report(log)
        assert report["total_incidents"] == 2
        assert report["incidents_by_severity"]["life_health"] == 1
        assert report["incidents_by_severity"]["other"] == 1

    def test_report_json_serializable(self, tmp_path):
        log = IncidentLog(tmp_path / "incidents.jsonl")
        log.record(IncidentSeverity.OTHER, "cat", "desc", {})
        report = generate_report(log)
        serialized = json.dumps(report)
        assert len(serialized) > 0

    def test_empty_log_report(self, tmp_path):
        log = IncidentLog(tmp_path / "incidents.jsonl")
        report = generate_report(log)
        assert report["total_incidents"] == 0
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_incidents.py -v
```

Expected: FAIL — `castor.incidents` does not exist.

- [ ] **Step 3: Create `castor/incidents.py`**

```python
"""castor.incidents — post-market monitoring incident log (EU AI Act Art. 72).

Provides a persistent JSONL-based incident log and Art. 72-structured report generator.

Usage:
    from castor.incidents import IncidentLog, IncidentSeverity, generate_report

    log = IncidentLog()  # default: ~/.opencastor/incidents.jsonl
    log.record(IncidentSeverity.LIFE_HEALTH, "estop_failure", "ESTOP triggered", state)
    report = generate_report(log)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

INCIDENT_SCHEMA_VERSION = "rcan-incidents-v1"
DEFAULT_INCIDENT_LOG_PATH = Path.home() / ".opencastor" / "incidents.jsonl"

# EU AI Act Art. 72 reporting deadlines:
# - life_health: 15 days from discovery
# - other: 3 months from discovery
REPORTING_DEADLINES_DAYS = {
    "life_health": 15,
    "other": 90,
}


class IncidentSeverity(str, Enum):
    LIFE_HEALTH = "life_health"  # Risk to life or health — 15-day reporting deadline
    OTHER = "other"              # All other serious incidents — 3-month deadline


class IncidentLog:
    """Persistent JSONL incident log for Art. 72 post-market monitoring.

    Each incident is stored as a JSON line in a JSONL file.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path else DEFAULT_INCIDENT_LOG_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        severity: IncidentSeverity,
        category: str,
        description: str,
        system_state: dict[str, Any],
    ) -> str:
        """Record a new incident. Returns the incident ID (UUID4)."""
        incident_id = str(uuid.uuid4())
        entry = {
            "id": incident_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": severity.value if isinstance(severity, IncidentSeverity) else str(severity),
            "category": category,
            "description": description,
            "system_state": system_state,
            "reported": False,
            "reporting_deadline_days": REPORTING_DEADLINES_DAYS.get(
                severity.value if isinstance(severity, IncidentSeverity) else str(severity),
                REPORTING_DEADLINES_DAYS["other"],
            ),
        }
        with open(self._path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        return incident_id

    def list_incidents(self) -> list[dict[str, Any]]:
        """Return all incidents from the log, oldest first."""
        if not self._path.exists():
            return []
        incidents = []
        with open(self._path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        incidents.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return incidents


def generate_report(log: IncidentLog) -> dict[str, Any]:
    """Generate an Art. 72-structured post-market monitoring report.

    The report covers: total incidents, breakdown by severity, full incident list,
    and reporting deadline guidance per EU AI Act Art. 72.
    """
    incidents = log.list_incidents()
    by_severity: dict[str, int] = {}
    for inc in incidents:
        sev = inc.get("severity", "other")
        by_severity[sev] = by_severity.get(sev, 0) + 1

    return {
        "schema": INCIDENT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_incidents": len(incidents),
        "incidents_by_severity": by_severity,
        "reporting_deadlines": REPORTING_DEADLINES_DAYS,
        "art72_note": (
            "EU AI Act Art. 72 requires providers of high-risk AI systems to report "
            "serious incidents to market surveillance authorities. "
            "life_health incidents: within 15 days. Other incidents: within 3 months."
        ),
        "incidents": incidents,
    }
```

- [ ] **Step 4: Run the tests**

```bash
pytest tests/test_incidents.py -v
```

Expected: All 12 tests PASS.

- [ ] **Step 5: Add `cmd_incidents` to `castor/cli.py`**

Add after `cmd_eu_register`:

```python
def cmd_incidents(args) -> None:
    """castor incidents — post-market monitoring incident log (EU AI Act Art. 72)."""
    import json as _json
    import sys
    from pathlib import Path

    from castor.incidents import IncidentLog, IncidentSeverity, generate_report

    incidents_cmd = getattr(args, "incidents_cmd", None)
    log_path = getattr(args, "log", None)
    log = IncidentLog(log_path) if log_path else IncidentLog()

    if incidents_cmd == "record":
        severity_str = getattr(args, "severity", "other")
        try:
            severity = IncidentSeverity(severity_str)
        except ValueError:
            print(f"Error: invalid severity {severity_str!r}. Use: life_health, other", file=sys.stderr)
            raise SystemExit(1)
        incident_id = log.record(
            severity=severity,
            category=getattr(args, "category", "unspecified"),
            description=getattr(args, "description", ""),
            system_state={},
        )
        print(f"Incident recorded: {incident_id}")

    elif incidents_cmd == "list":
        incidents = log.list_incidents()
        if not incidents:
            print("No incidents recorded.")
        else:
            for inc in incidents:
                print(f"[{inc['timestamp']}] [{inc['severity'].upper()}] {inc['category']}: {inc['description']}")

    elif incidents_cmd == "report":
        report = generate_report(log)
        output = getattr(args, "output", None)
        if output:
            with open(output, "w") as f:
                _json.dump(report, f, indent=2, default=str)
            print(f"Report written to: {output}")
        else:
            print(_json.dumps(report, indent=2, default=str))

    else:
        print("Usage: castor incidents {record|list|report}", file=sys.stderr)
        raise SystemExit(1)
```

Add subparser (near the `eu-register` subparser):

```python
# ── incidents ─────────────────────────────────────────────────────────────────
p_incidents = sub.add_parser(
    "incidents",
    help="Post-market monitoring incident log (EU AI Act Art. 72)",
)
p_incidents_sub = p_incidents.add_subparsers(dest="incidents_cmd")
p_incidents.add_argument("--log", metavar="FILE", help="Incident log path (default: ~/.opencastor/incidents.jsonl)")
p_incidents.set_defaults(func=cmd_incidents)

p_incidents_record = p_incidents_sub.add_parser("record", help="Record a new incident")
p_incidents_record.add_argument(
    "--severity", choices=["life_health", "other"], default="other",
    help="Incident severity (life_health: 15-day deadline; other: 3-month deadline)"
)
p_incidents_record.add_argument("--category", required=True, help="Incident category (e.g. estop_failure)")
p_incidents_record.add_argument("--description", required=True, help="Human-readable description")

p_incidents_sub.add_parser("list", help="List all recorded incidents")

p_incidents_report = p_incidents_sub.add_parser("report", help="Generate Art. 72 incident report")
p_incidents_report.add_argument("--output", metavar="FILE", help="Output JSON path (default: stdout)")
```

- [ ] **Step 6: Add CLI tests**

Add to `tests/test_cli.py`:

```python
class TestIncidentsCli:
    def test_help_exits_0(self):
        result = subprocess.run(
            ["python", "-m", "castor.cli", "incidents", "--help"],
            capture_output=True, text=True
        )
        assert result.returncode == 0

    def test_record_subcommand_help(self):
        result = subprocess.run(
            ["python", "-m", "castor.cli", "incidents", "record", "--help"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "--severity" in result.stdout

    def test_report_subcommand_writes_json(self, tmp_path):
        log_path = str(tmp_path / "test.jsonl")
        output_path = str(tmp_path / "report.json")
        result = subprocess.run(
            ["python", "-m", "castor.cli", "incidents", "--log", log_path,
             "report", "--output", output_path],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        import json
        with open(output_path) as f:
            report = json.load(f)
        assert report["schema"] == "rcan-incidents-v1"
        assert report["total_incidents"] == 0
```

- [ ] **Step 7: Run all tests**

```bash
pytest tests/test_incidents.py tests/test_cli.py -v
```

Expected: All pass.

- [ ] **Step 8: Commit**

```bash
git add castor/incidents.py castor/cli.py tests/test_incidents.py tests/test_cli.py
git commit -m "feat: castor incidents — Art. 72 post-market monitoring incident log and report"
```

---

## Task 5: Art. 10 Model Provenance + Art. 11 Annex IV Coverage in FRIA

Add `model_provenance` (Art. 10) and `annex_iv_coverage` (Art. 11) blocks to `build_fria_document`. Both are derived from existing config data — no new parameters needed.

**Files:**
- Modify: `castor/fria.py` — `build_fria_document`
- Modify: `tests/test_fria.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_fria.py`:

```python
class TestFriaModelProvenance:
    """Art. 10 — model provenance block in FRIA."""

    def _build(self, config=None):
        from castor.fria import build_fria_document
        cfg = config or {
            "rcan_version": "2.2",
            "metadata": {"rrn": "RRN-000000000001"},
            "reactive": {"min_obstacle_m": 0.3},
            "agent": {"provider": "google", "model": "gemini-2.5-flash"},
        }
        with patch("castor.fria.ConformanceChecker") as MockCC:
            MockCC.return_value.run_all.return_value = []
            MockCC.return_value.summary.return_value = {"score": 90, "pass": 5, "warn": 0, "fail": 0}
            return build_fria_document(cfg, "safety_component", "Indoor nav")

    def test_model_provenance_block_present(self):
        doc = self._build()
        assert "model_provenance" in doc

    def test_model_provenance_provider(self):
        doc = self._build()
        assert doc["model_provenance"]["provider"] == "google"

    def test_model_provenance_model(self):
        doc = self._build()
        assert doc["model_provenance"]["model"] == "gemini-2.5-flash"

    def test_model_provenance_art10_note(self):
        doc = self._build()
        assert "art10_responsibility" in doc["model_provenance"]
        assert doc["model_provenance"]["art10_responsibility"] == "upstream_ai_provider"


class TestFriaAnnexIVCoverage:
    """Art. 11 — Annex IV coverage table in FRIA."""

    def _build(self):
        from castor.fria import build_fria_document
        cfg = {
            "rcan_version": "2.2",
            "metadata": {"rrn": "RRN-000000000001"},
            "reactive": {"min_obstacle_m": 0.3},
            "agent": {"provider": "google", "model": "gemini-2.5-flash"},
        }
        with patch("castor.fria.ConformanceChecker") as MockCC:
            MockCC.return_value.run_all.return_value = []
            MockCC.return_value.summary.return_value = {"score": 90, "pass": 5, "warn": 0, "fail": 0}
            return build_fria_document(cfg, "safety_component", "Indoor nav")

    def test_annex_iv_coverage_present(self):
        doc = self._build()
        assert "annex_iv_coverage" in doc

    def test_annex_iv_coverage_is_list(self):
        doc = self._build()
        assert isinstance(doc["annex_iv_coverage"], list)

    def test_annex_iv_has_9_points(self):
        """EU AI Act Annex IV has 9 documentation points."""
        doc = self._build()
        assert len(doc["annex_iv_coverage"]) == 9

    def test_each_entry_has_point_title_status(self):
        doc = self._build()
        for entry in doc["annex_iv_coverage"]:
            assert "point" in entry
            assert "title" in entry
            assert "status" in entry

    def test_point_numbers_sequential(self):
        doc = self._build()
        points = [e["point"] for e in doc["annex_iv_coverage"]]
        assert points == list(range(1, 10))
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_fria.py::TestFriaModelProvenance tests/test_fria.py::TestFriaAnnexIVCoverage -v
```

Expected: FAIL — `model_provenance` and `annex_iv_coverage` keys not in FRIA document.

- [ ] **Step 3: Add `model_provenance` and `annex_iv_coverage` to `build_fria_document` in `castor/fria.py`**

Define the Annex IV coverage table as a module-level constant (add after `ANNEX_III_BASES`):

```python
ANNEX_IV_COVERAGE = [
    {"point": 1, "title": "General description of the AI system",
     "fria_field": "system", "status": "covered"},
    {"point": 2, "title": "Detailed description of elements and development process",
     "fria_field": "conformance", "status": "covered"},
    {"point": 3, "title": "Monitoring, functioning, and control measures",
     "fria_field": "human_oversight", "status": "covered"},
    {"point": 4, "title": "Performance metrics and validation results",
     "fria_field": "safety_benchmarks", "status": "covered_when_benchmark_provided"},
    {"point": 5, "title": "Risk management system (Art. 9)",
     "fria_field": "hardware_observations", "status": "covered"},
    {"point": 6, "title": "Changes made throughout the lifecycle",
     "fria_field": None, "status": "deployer_responsibility"},
    {"point": 7, "title": "Applied harmonised standards",
     "fria_field": None, "status": "partial_p66_iso10218"},
    {"point": 8, "title": "EU declaration of conformity",
     "fria_field": None, "status": "deployer_responsibility"},
    {"point": 9, "title": "Instructions for use",
     "fria_field": None, "status": "requires_ifu_command"},
]
```

In `build_fria_document`, add to the returned dict (after `"hardware_observations"`):

```python
        "model_provenance": {
            "provider": agent_cfg.get("provider", ""),
            "model": agent_cfg.get("model", ""),
            "art10_responsibility": "upstream_ai_provider",
            "note": (
                "EU AI Act Art. 10 data governance obligations for training data apply "
                "to the upstream AI provider (e.g. Anthropic, Google, OpenAI), not the "
                "OpenCastor deployer. Deployer responsibility: pin model version and "
                "document the provider's Art. 10 compliance status."
            ),
        },
        "annex_iv_coverage": ANNEX_IV_COVERAGE,
```

- [ ] **Step 4: Run the tests**

```bash
pytest tests/test_fria.py::TestFriaModelProvenance tests/test_fria.py::TestFriaAnnexIVCoverage -v
```

Expected: All 9 tests PASS.

- [ ] **Step 5: Run full FRIA test suite**

```bash
pytest tests/test_fria.py -v
```

Expected: All pass, no regressions.

- [ ] **Step 6: Commit**

```bash
git add castor/fria.py tests/test_fria.py
git commit -m "feat: FRIA model_provenance (Art. 10) and annex_iv_coverage (Art. 11) blocks"
```

---

## Task 6: Art. 17 QMS Declaration + `rcan_v22.qms_declaration` Check

Add optional `qms_reference` field to `build_fria_document` and a new conformance check `rcan_v22.qms_declaration` that warns when absent.

**Files:**
- Modify: `castor/fria.py` — `build_fria_document`
- Modify: `castor/conformance.py` — `_check_rcan_v21` + new `_v22_qms_declaration` method
- Modify: `castor/cli.py` — `castor fria generate --qms-reference`
- Modify: `tests/test_fria.py`
- Modify: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_fria.py`:

```python
class TestFriaQmsReference:
    """Art. 17 QMS declaration in FRIA."""

    def _build(self, qms_reference=None):
        from castor.fria import build_fria_document
        cfg = {
            "rcan_version": "2.2",
            "metadata": {"rrn": "RRN-000000000001"},
            "reactive": {"min_obstacle_m": 0.3},
            "agent": {"provider": "google", "model": "gemini-2.5-flash"},
        }
        with patch("castor.fria.ConformanceChecker") as MockCC:
            MockCC.return_value.run_all.return_value = []
            MockCC.return_value.summary.return_value = {"score": 90, "pass": 5, "warn": 0, "fail": 0}
            return build_fria_document(cfg, "safety_component", "nav", qms_reference=qms_reference)

    def test_qms_reference_absent_when_not_provided(self):
        doc = self._build()
        assert "qms_reference" not in doc

    def test_qms_reference_present_when_provided(self):
        doc = self._build(qms_reference="https://example.com/qms/v1.pdf")
        assert doc["qms_reference"] == "https://example.com/qms/v1.pdf"
```

Add to `tests/test_conformance.py`:

```python
class TestQmsDeclarationCheck:
    """rcan_v22.qms_declaration — Art. 17 QMS conformance check."""

    def _checker(self, extra=None):
        config = {
            "rcan_version": "2.2",
            "metadata": {"rrn": "RRN-000000000001"},
            "reactive": {"min_obstacle_m": 0.3},
            "agent": {"provider": "google", "model": "gemini-2.5-flash"},
        }
        if extra:
            config.update(extra)
        return ConformanceChecker(config)

    def test_warns_when_qms_reference_absent(self):
        results = self._checker().run_category("rcan_v21")
        qms = next((r for r in results if r.check_id == "rcan_v22.qms_declaration"), None)
        assert qms is not None
        assert qms.status == "warn"

    def test_passes_when_qms_reference_set(self):
        results = self._checker({"qms_reference": "https://example.com/qms.pdf"}).run_category("rcan_v21")
        qms = next(r for r in results if r.check_id == "rcan_v22.qms_declaration")
        assert qms.status == "pass"

    def test_check_in_rcan_v22_category(self):
        results = self._checker().run_category("rcan_v21")
        qms = next(r for r in results if r.check_id == "rcan_v22.qms_declaration")
        assert qms.category == "rcan_v22"
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_fria.py::TestFriaQmsReference tests/test_conformance.py::TestQmsDeclarationCheck -v
```

Expected: FAIL — `qms_reference` param and `rcan_v22.qms_declaration` check do not exist.

- [ ] **Step 3: Add `qms_reference` to `build_fria_document` in `castor/fria.py`**

Update the function signature:

```python
def build_fria_document(
    config: dict,
    annex_iii_basis: str,
    intended_use: str,
    memory_path: str | None = None,
    prerequisite_waived: bool = False,
    benchmark_path: str | None = None,
    annex_iii_strict: bool = False,
    qms_reference: str | None = None,
) -> dict:
```

In the returned dict, add after `"annex_iv_coverage"`:

```python
        **({"qms_reference": qms_reference} if qms_reference else {}),
```

- [ ] **Step 4: Add `_v22_qms_declaration` to `castor/conformance.py`**

```python
def _v22_qms_declaration(self) -> ConformanceResult:
    """RCAN v2.2 §17 — Quality Management System reference (EU AI Act Art. 17)."""
    cid = "rcan_v22.qms_declaration"
    qms_ref = self._cfg.get("qms_reference", None)
    if qms_ref:
        return ConformanceResult(
            check_id=cid,
            category="rcan_v22",
            status="pass",
            detail=f"QMS reference declared: {qms_ref}",
        )
    return ConformanceResult(
        check_id=cid,
        category="rcan_v22",
        status="warn",
        detail=(
            "No QMS reference declared — EU AI Act Art. 17 requires a quality management "
            "system for high-risk AI providers"
        ),
        fix=(
            "Add `qms_reference: <uri-or-hash>` to your RCAN config pointing to your "
            "Art. 17 QMS documentation. See rcan-spec/docs/compliance/art17-qms-template.md"
        ),
    )
```

Wire into `_check_rcan_v21`:

```python
def _check_rcan_v21(self) -> list[ConformanceResult]:
    return [
        self._v21_firmware_manifest(),
        self._v21_sbom_attestation(),
        self._v21_authority_handler(),
        self._v21_audit_chain_retention(),
        self._v21_rcan_version(),
        self._v22_pq_signing_key(),
        self._v22_firmware_pq_sig(),
        self._v22_watermark_enforced(),
        self._v22_qms_declaration(),
    ]
```

- [ ] **Step 5: Add `--qms-reference` to `castor fria generate` in `castor/cli.py`**

In the fria generate subparser section, add:

```python
p_fria_gen.add_argument(
    "--qms-reference",
    dest="qms_reference",
    metavar="URI",
    help="URI or hash of the Art. 17 Quality Management System document",
)
```

In `cmd_fria_generate`, pass through:

```python
doc = build_fria_document(
    config=config,
    annex_iii_basis=annex_iii,
    intended_use=intended_use,
    memory_path=memory_path,
    prerequisite_waived=prerequisite_waived,
    benchmark_path=getattr(args, "benchmark_path", None),
    annex_iii_strict=annex_iii_strict,
    qms_reference=getattr(args, "qms_reference", None),
)
```

- [ ] **Step 6: Run all tests**

```bash
pytest tests/test_fria.py tests/test_conformance.py -v
```

Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add castor/fria.py castor/conformance.py castor/cli.py tests/test_fria.py tests/test_conformance.py
git commit -m "feat: Art. 17 QMS declaration — qms_reference in FRIA and rcan_v22.qms_declaration check"
```

---

## Task 7: Art. 13 Instructions for Use Document

Add `castor ifu generate` command that produces an Art. 13-structured "Instructions for Use" HTML/JSON document from RCAN config + P66 manifest + FRIA data. New `castor/instructions_for_use.py` module.

**Files:**
- Create: `castor/instructions_for_use.py`
- Modify: `castor/cli.py`
- Create: `tests/test_instructions_for_use.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_instructions_for_use.py`:

```python
"""Tests for castor.instructions_for_use — EU AI Act Art. 13 IFU document."""
import json

import pytest

from castor.instructions_for_use import build_ifu_document, IFU_SCHEMA_VERSION


SAMPLE_CONFIG = {
    "rcan_version": "2.2",
    "metadata": {
        "rrn": "RRN-000000000001",
        "robot_name": "test-robot",
        "provider_name": "Test Corp",
        "provider_contact": "safety@testcorp.com",
    },
    "agent": {"provider": "google", "model": "gemini-2.5-flash"},
}


class TestBuildIfuDocument:
    def test_returns_dict_with_required_art13_fields(self):
        doc = build_ifu_document(SAMPLE_CONFIG, "safety_component", "Indoor navigation")
        assert "schema" in doc
        assert "provider_identity" in doc
        assert "intended_purpose" in doc
        assert "capabilities_and_limitations" in doc
        assert "human_oversight_measures" in doc
        assert "known_risks_and_misuse" in doc
        assert "expected_lifetime" in doc

    def test_schema_value(self):
        doc = build_ifu_document(SAMPLE_CONFIG, "safety_component", "Indoor navigation")
        assert doc["schema"] == IFU_SCHEMA_VERSION

    def test_provider_identity_from_config(self):
        doc = build_ifu_document(SAMPLE_CONFIG, "safety_component", "Indoor navigation")
        assert doc["provider_identity"]["rrn"] == "RRN-000000000001"
        assert doc["provider_identity"]["robot_name"] == "test-robot"

    def test_intended_purpose_in_output(self):
        doc = build_ifu_document(SAMPLE_CONFIG, "safety_component", "Indoor navigation for warehouse")
        assert doc["intended_purpose"]["description"] == "Indoor navigation for warehouse"
        assert doc["intended_purpose"]["annex_iii_basis"] == "safety_component"

    def test_json_serializable(self):
        doc = build_ifu_document(SAMPLE_CONFIG, "safety_component", "Indoor navigation")
        serialized = json.dumps(doc)
        assert len(serialized) > 0

    def test_human_oversight_section_present(self):
        doc = build_ifu_document(SAMPLE_CONFIG, "safety_component", "nav")
        ho = doc["human_oversight_measures"]
        assert "hitl_gates" in ho
        assert "estop" in ho
        assert "confidence_gates" in ho
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_instructions_for_use.py -v
```

Expected: FAIL — `castor.instructions_for_use` does not exist.

- [ ] **Step 3: Create `castor/instructions_for_use.py`**

```python
"""castor.instructions_for_use — Art. 13 Instructions for Use document generator.

Generates an EU AI Act Art. 13-structured Instructions for Use document from
RCAN config and deployment context. The document covers all fields required
by Art. 13(3) of the EU AI Act for high-risk AI systems.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

IFU_SCHEMA_VERSION = "rcan-ifu-v1"

# EU AI Act Art. 13(3) required fields
ART13_FIELDS = [
    "provider_identity",
    "intended_purpose",
    "capabilities_and_limitations",
    "accuracy_and_performance",
    "human_oversight_measures",
    "known_risks_and_misuse",
    "expected_lifetime",
    "maintenance_requirements",
]


def build_ifu_document(
    config: dict,
    annex_iii_basis: str,
    intended_use: str,
) -> dict[str, Any]:
    """Build an Art. 13-structured Instructions for Use document.

    Args:
        config:          Parsed RCAN config dict.
        annex_iii_basis: EU AI Act Annex III classification.
        intended_use:    Deployment description.

    Returns:
        IFU document dict ready for JSON serialization or HTML rendering.
    """
    meta = config.get("metadata", {}) or {}
    agent_cfg = config.get("agent", {}) or {}
    safety_cfg = config.get("safety", {}) or {}

    return {
        "schema": IFU_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "art13_coverage": ART13_FIELDS,
        # Art. 13(3)(a) — provider identity
        "provider_identity": {
            "rrn": meta.get("rrn", ""),
            "rrn_uri": meta.get("rrn_uri", ""),
            "robot_name": meta.get("robot_name", ""),
            "provider_name": meta.get("provider_name", ""),
            "provider_contact": meta.get("provider_contact", ""),
            "rcan_version": config.get("rcan_version", ""),
            "agent_provider": agent_cfg.get("provider", ""),
            "agent_model": agent_cfg.get("model", ""),
        },
        # Art. 13(3)(b) — intended purpose
        "intended_purpose": {
            "description": intended_use,
            "annex_iii_basis": annex_iii_basis,
            "deployment_context": "High-risk AI system under EU AI Act Annex III",
        },
        # Art. 13(3)(c) — capabilities and limitations
        "capabilities_and_limitations": {
            "summary": (
                "OpenCastor is a universal robot runtime that connects LLM AI providers "
                "to physical robot hardware. It enforces safety constraints via SafetyLayer, "
                "BoundsChecker, and HiTL authorization gates."
            ),
            "known_limitations": [
                "AI provider responses are subject to model confidence thresholds",
                "Physical hardware limits enforced by BoundsChecker configuration",
                "HiTL authorization required for high-risk actions",
                "Wireless connectivity required for remote monitoring",
            ],
        },
        # Art. 13(3)(d) — accuracy and performance
        "accuracy_and_performance": {
            "note": (
                "Quantified performance evidence is available via `castor safety benchmark`. "
                "Safety path P95 latency thresholds: ESTOP 100ms, BoundsCheck 5ms, "
                "ConfidenceGate 2ms, FullPipeline 50ms."
            ),
        },
        # Art. 13(3)(e) — human oversight measures
        "human_oversight_measures": {
            "hitl_gates": "Human-in-the-loop authorization gates (RCAN §8) prevent autonomous high-risk actions",
            "estop": "Emergency stop (ESTOP) halts all motion; P95 latency ≤ 100ms",
            "confidence_gates": "AI commands below confidence threshold are blocked automatically",
            "override": "Operators can override or halt the system at any time via ESTOP",
        },
        # Art. 13(3)(f) — foreseeable misuse
        "known_risks_and_misuse": {
            "foreseeable_misuse": [
                "Deployment in environments outside the declared intended use",
                "Operating beyond configured physical bounds",
                "Disabling HiTL gates without risk assessment",
                "Using uncertified AI providers without Art. 10 documentation",
            ],
            "mitigations": [
                "BoundsChecker enforces hard physical limits",
                "Conformance checks detect disabled safety features",
                "Anti-subversion module defends against prompt injection",
            ],
        },
        # Art. 13(3)(g) — expected lifetime
        "expected_lifetime": {
            "software_support": "Subject to OpenCastor release lifecycle (YYYY.MM.DD versioning)",
            "hardware_dependent": True,
            "note": "Deployer is responsible for post-market monitoring per Art. 72",
        },
        # Art. 13(3)(h) — maintenance
        "maintenance_requirements": {
            "software_updates": "Run `castor upgrade` for runtime updates; monitor CHANGELOG.md",
            "conformance_checks": "Run `castor validate` before each deployment",
            "incident_logging": "Run `castor incidents record` for any safety-relevant events",
        },
    }
```

- [ ] **Step 4: Run the tests**

```bash
pytest tests/test_instructions_for_use.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Add `castor ifu generate` to `castor/cli.py`**

```python
def cmd_ifu(args) -> None:
    """castor ifu — EU AI Act Art. 13 Instructions for Use document."""
    import json as _json
    import sys
    from pathlib import Path

    import yaml

    from castor.fria import ANNEX_III_BASES
    from castor.instructions_for_use import build_ifu_document

    ifu_cmd = getattr(args, "ifu_cmd", None)
    if ifu_cmd != "generate":
        print("Usage: castor ifu generate --config ... --annex-iii ... --intended-use ...", file=sys.stderr)
        raise SystemExit(1)

    config_path = getattr(args, "config", None) or "robot.rcan.yaml"
    if not Path(config_path).exists():
        print(f"Error: config not found: {config_path!r}", file=sys.stderr)
        raise SystemExit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    annex_iii = getattr(args, "annex_iii", None)
    if not annex_iii or annex_iii not in ANNEX_III_BASES:
        print(f"Error: --annex-iii required. Valid: {', '.join(sorted(ANNEX_III_BASES))}", file=sys.stderr)
        raise SystemExit(1)

    doc = build_ifu_document(config, annex_iii, getattr(args, "intended_use", "") or "")

    output = getattr(args, "output", None)
    if output:
        with open(output, "w") as f:
            _json.dump(doc, f, indent=2, default=str)
        print(f"Instructions for Use written to: {output}")
    else:
        print(_json.dumps(doc, indent=2, default=str))
```

Add subparser:

```python
# ── ifu ───────────────────────────────────────────────────────────────────────
p_ifu = sub.add_parser("ifu", help="EU AI Act Art. 13 Instructions for Use document")
p_ifu_sub = p_ifu.add_subparsers(dest="ifu_cmd")
p_ifu.set_defaults(func=cmd_ifu)
p_ifu_gen = p_ifu_sub.add_parser("generate", help="Generate Art. 13 Instructions for Use document")
p_ifu_gen.add_argument("--config", metavar="FILE", default="robot.rcan.yaml")
p_ifu_gen.add_argument("--annex-iii", dest="annex_iii", required=True, metavar="BASIS")
p_ifu_gen.add_argument("--intended-use", dest="intended_use", required=True, metavar="TEXT")
p_ifu_gen.add_argument("--output", metavar="FILE", help="Output JSON path (default: stdout)")
```

- [ ] **Step 6: Add CLI tests**

```python
class TestIfuCli:
    def test_help_exits_0(self):
        result = subprocess.run(
            ["python", "-m", "castor.cli", "ifu", "generate", "--help"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "--annex-iii" in result.stdout
```

- [ ] **Step 7: Run all tests**

```bash
pytest tests/test_instructions_for_use.py tests/test_cli.py -v
```

Expected: All pass.

- [ ] **Step 8: Commit**

```bash
git add castor/instructions_for_use.py castor/cli.py tests/test_instructions_for_use.py tests/test_cli.py
git commit -m "feat: castor ifu generate — Art. 13 Instructions for Use document generator"
```

---

## Task 8: Full Test Suite + Lint

Run the complete test suite and lint to confirm zero regressions across all 7 tasks.

**Files:** No changes — validation only.

- [ ] **Step 1: Run full test suite**

```bash
cd /home/craigm26/OpenCastor
pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All tests pass (7804+ tests). If any new test fails, fix it before proceeding.

- [ ] **Step 2: Run ruff lint**

```bash
ruff check castor/conformance.py castor/fria.py castor/eu_register.py castor/incidents.py castor/instructions_for_use.py castor/cli.py
```

Expected: No errors. Fix any lint errors that appear.

- [ ] **Step 3: Run ruff format check**

```bash
ruff format --check castor/conformance.py castor/fria.py castor/eu_register.py castor/incidents.py castor/instructions_for_use.py castor/cli.py
```

If format errors appear:

```bash
ruff format castor/conformance.py castor/fria.py castor/eu_register.py castor/incidents.py castor/instructions_for_use.py castor/cli.py
git add -u
git commit -m "style: ruff format EU AI Act compliance modules"
```

- [ ] **Step 4: Final commit if any format fixes**

Only commit if Step 3 required changes. Otherwise skip.

```bash
git log --oneline -8
```

Expected output (8 commits in this feature branch):
```
<hash> style: ruff format EU AI Act compliance modules (if needed)
<hash> feat: castor ifu generate — Art. 13 Instructions for Use document generator
<hash> feat: Art. 17 QMS declaration — qms_reference in FRIA and rcan_v22.qms_declaration check
<hash> feat: FRIA model_provenance (Art. 10) and annex_iv_coverage (Art. 11) blocks
<hash> feat: castor incidents — Art. 72 post-market monitoring incident log and report
<hash> feat: castor eu-register — Art. 49 EU AI Act database submission package generator
<hash> feat: rcan_v22.watermark_enforced — Art. 50 watermark enforcement conformance check
<hash> feat: Art. 16 Annex III strict mode — promote SBOM/firmware/authority to fail for high-risk systems
```

---

## Spec Coverage Check

| Spec Gap | Task |
|---|---|
| Art. 16 — SBOM/firmware/authority warn→fail for Annex III | Task 1 |
| Art. 50 — Watermark not enforced by default | Task 2 |
| Art. 49 — No EU AI Act database submission tooling | Task 3 |
| Art. 72 — No post-market monitoring | Task 4 |
| Art. 10 — No model provenance in FRIA | Task 5 |
| Art. 11(b) — No Annex IV coverage table | Task 5 |
| Art. 17 — No QMS declaration in FRIA | Task 6 |
| Art. 13 — No Instructions for Use document | Task 7 |
| Art. 11(a) — §22 spec page (rcan-spec repo) | Out of scope for this plan — separate rcan-spec PR |
