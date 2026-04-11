"""FRIA document generation for EU AI Act compliance (RCAN §22).

Provides:
    check_fria_prerequisite  — conformance gate (score >= 80, 0 safety fails)
    build_fria_document      — assemble unsigned FRIA JSON document
    sign_fria                — add ML-DSA-65 signature
    render_fria_html         — render Jinja2 HTML companion
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from castor.conformance import ConformanceChecker, ConformanceResult

logger = logging.getLogger("OpenCastor.FRIA")

FRIA_SCHEMA_VERSION = "rcan-fria-v1"
FRIA_SPEC_REF = "https://rcan.dev/spec/section-22"
CONFORMANCE_SCORE_MIN = 80
MEMORY_CONFIDENCE_MIN = 0.30

ANNEX_III_BASES = frozenset({
    "safety_component",
    "biometric",
    "critical_infrastructure",
    "education",
    "employment",
    "essential_services",
    "law_enforcement",
    "migration",
    "administration_of_justice",
    "general_purpose_ai",
})


def check_fria_prerequisite(
    config: dict,
) -> tuple[bool, list[ConformanceResult]]:
    """Run conformance checks and return (gate_passed, blocking_results).

    Gate passes when conformance score >= 80 and there are zero safety.* failures.
    """
    checker = ConformanceChecker(config)
    results = checker.run_all()
    summary = checker.summary(results)

    safety_failures = [
        r for r in results if r.category == "safety" and r.status == "fail"
    ]
    score_ok = summary["score"] >= CONFORMANCE_SCORE_MIN
    gate_passed = score_ok and len(safety_failures) == 0

    if not gate_passed:
        # Return all failures when score gate failed; safety failures when score ok
        blocking = [r for r in results if r.status == "fail"] if not score_ok else safety_failures
    else:
        blocking = []

    return gate_passed, blocking


def build_fria_document(
    config: dict,
    annex_iii_basis: str,
    intended_use: str,
    memory_path: str | None = None,
    prerequisite_waived: bool = False,
) -> dict:
    """Assemble the unsigned FRIA JSON document dict.

    Args:
        config:              Parsed RCAN config dict.
        annex_iii_basis:     EU AI Act Annex III classification. Must be one of
                             ANNEX_III_BASES.
        intended_use:        Free-text deployment description.
        memory_path:         Path to robot-memory.md. HARDWARE_OBSERVATION entries
                             with confidence >= 0.30 are included.
        prerequisite_waived: True when --force was passed; recorded in the document.

    Returns:
        Unsigned FRIA document dict (no 'sig' or 'signing_key' fields).
    """
    if annex_iii_basis not in ANNEX_III_BASES:
        raise ValueError(
            f"Invalid annex_iii_basis: {annex_iii_basis!r}. "
            f"Must be one of: {', '.join(sorted(ANNEX_III_BASES))}"
        )

    meta = config.get("metadata", {})
    agent_cfg = config.get("agent", {})

    try:
        import importlib.metadata as _imd
        oc_version = _imd.version("opencastor")
    except Exception:
        oc_version = "unknown"

    # Run conformance
    checker = ConformanceChecker(config)
    results = checker.run_all()
    summary = checker.summary(results)

    # Derive human_oversight from conformance results
    check_map = {r.check_id: r for r in results}

    def _passed(*check_ids: str) -> bool:
        # check_ids are aliases for the same gate — pass if any alias is found passing
        return any(
            check_map.get(cid) is not None and check_map[cid].status == "pass"
            for cid in check_ids
        )

    human_oversight = {
        "hitl_configured": _passed(
            "safety.hitl_authorization_configured", "safety.hitl_configured"
        ),
        "confidence_gates_configured": _passed("safety.confidence_gates_configured"),
        "estop_configured": _passed("safety.estop_configured", "safety.estop_capable"),
    }

    # Hardware observations from robot memory
    hardware_observations: list[dict[str, Any]] = []
    if memory_path and os.path.exists(memory_path):
        try:
            from castor.brain.memory_schema import EntryType, load_memory

            memory = load_memory(memory_path)
            hardware_observations = [
                {
                    "id": e.id,
                    "text": e.text,
                    "confidence": round(e.confidence, 3),
                    "tags": e.tags,
                }
                for e in memory.entries
                if e.type == EntryType.HARDWARE_OBSERVATION
                and e.confidence >= MEMORY_CONFIDENCE_MIN
            ]
        except Exception as exc:
            logger.warning("Could not load robot memory from %s: %s", memory_path, exc)

    return {
        "schema": FRIA_SCHEMA_VERSION,
        "spec_ref": FRIA_SPEC_REF,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system": {
            "rrn": meta.get("rrn", ""),
            "rrn_uri": meta.get("rrn_uri", ""),
            "robot_name": meta.get("robot_name", ""),
            "opencastor_version": oc_version,
            "rcan_version": meta.get("rcan_version", config.get("rcan_version", "")),
            "agent_provider": agent_cfg.get("provider", ""),
            "agent_model": agent_cfg.get("model", ""),
        },
        "deployment": {
            "annex_iii_basis": annex_iii_basis,
            "intended_use": intended_use,
            "prerequisite_waived": prerequisite_waived,
        },
        "conformance": {
            "score": summary["score"],
            "pass": summary["pass"],
            "warn": summary["warn"],
            "fail": summary["fail"],
            "checks": [
                {
                    "check_id": r.check_id,
                    "category": r.category,
                    "status": r.status,
                    "detail": r.detail,
                    **({"fix": r.fix} if r.fix else {}),
                }
                for r in results
            ],
        },
        "human_oversight": human_oversight,
        "hardware_observations": hardware_observations,
    }


def sign_fria(document: dict, config: dict) -> dict:
    """Add ML-DSA-65 signature to the FRIA document. (Task 2)"""
    raise NotImplementedError("sign_fria not yet implemented")


def render_fria_html(document: dict, template_path: str | None = None) -> str:
    """Render the FRIA document to an HTML string using the Jinja2 template. (Task 2)"""
    raise NotImplementedError("render_fria_html not yet implemented")
