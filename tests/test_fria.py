"""Tests for castor/fria.py — FRIA document generation (§22)."""
import json
from unittest.mock import MagicMock, patch

import pytest

# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_result(check_id, category, status, detail="ok", fix=None):
    from castor.conformance import ConformanceResult
    return ConformanceResult(
        check_id=check_id,
        category=category,
        status=status,
        detail=detail,
        fix=fix,
    )


def _make_config(rrn="RRN-000000000001"):
    return {
        "rcan_version": "1.9.0",
        "metadata": {
            "rrn": rrn,
            "rrn_uri": "rrn://test/robot/model/001",
            "robot_name": "test-bot",
        },
        "agent": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
    }


# ── check_fria_prerequisite ───────────────────────────────────────────────────

class TestCheckFriaPrerequisite:
    def _mock_checker(self, results, score):
        checker = MagicMock()
        checker.run_all.return_value = results
        checker.summary.return_value = {
            "pass": sum(1 for r in results if r.status == "pass"),
            "warn": sum(1 for r in results if r.status == "warn"),
            "fail": sum(1 for r in results if r.status == "fail"),
            "score": score,
        }
        return checker

    def test_passes_when_score_ok_and_no_safety_failures(self):
        from castor.fria import check_fria_prerequisite
        results = [
            _make_result("safety.estop_configured", "safety", "pass"),
            _make_result("protocol.rcan_version", "protocol", "pass"),
        ]
        with patch("castor.fria.ConformanceChecker", return_value=self._mock_checker(results, 90)):
            passed, blocking = check_fria_prerequisite(_make_config())
        assert passed is True
        assert blocking == []

    def test_blocked_by_low_score(self):
        from castor.fria import check_fria_prerequisite
        results = [
            _make_result("protocol.rcan_version", "protocol", "fail", fix="Update RCAN version"),
            _make_result("protocol.other", "protocol", "fail"),
        ]
        with patch("castor.fria.ConformanceChecker", return_value=self._mock_checker(results, 60)):
            passed, blocking = check_fria_prerequisite(_make_config())
        assert passed is False
        assert len(blocking) == 2

    def test_blocked_by_safety_failure_even_if_score_ok(self):
        from castor.fria import check_fria_prerequisite
        results = [
            _make_result("safety.estop_configured", "safety", "fail", fix="Configure ESTOP"),
            _make_result("protocol.rcan_version", "protocol", "pass"),
        ]
        with patch("castor.fria.ConformanceChecker", return_value=self._mock_checker(results, 85)):
            passed, blocking = check_fria_prerequisite(_make_config())
        assert passed is False
        assert any(r.check_id == "safety.estop_configured" for r in blocking)


# ── build_fria_document ───────────────────────────────────────────────────────

class TestBuildFriaDocument:
    def _patched_checker(self, score=87):
        results = [
            _make_result("safety.estop_configured", "safety", "pass"),
            _make_result("safety.confidence_gates_configured", "safety", "warn", fix="Set threshold"),
        ]
        checker = MagicMock()
        checker.run_all.return_value = results
        checker.summary.return_value = {"pass": 1, "warn": 1, "fail": 0, "score": score}
        return checker

    def test_returns_dict_with_required_top_level_keys(self):
        from castor.fria import build_fria_document
        with patch("castor.fria.ConformanceChecker", return_value=self._patched_checker()):
            doc = build_fria_document(_make_config(), "safety_component", "indoor nav")
        for key in ("schema", "spec_ref", "generated_at", "system", "deployment",
                    "conformance", "human_oversight", "hardware_observations"):
            assert key in doc, f"Missing top-level key: {key}"

    def test_schema_version_and_spec_ref(self):
        from castor.fria import FRIA_SCHEMA_VERSION, FRIA_SPEC_REF, build_fria_document
        with patch("castor.fria.ConformanceChecker", return_value=self._patched_checker()):
            doc = build_fria_document(_make_config(), "safety_component", "indoor nav")
        assert doc["schema"] == FRIA_SCHEMA_VERSION
        assert doc["spec_ref"] == FRIA_SPEC_REF

    def test_system_fields_populated_from_config(self):
        from castor.fria import build_fria_document
        with patch("castor.fria.ConformanceChecker", return_value=self._patched_checker()):
            doc = build_fria_document(_make_config(), "safety_component", "indoor nav")
        assert doc["system"]["rrn"] == "RRN-000000000001"
        assert doc["system"]["robot_name"] == "test-bot"
        assert doc["system"]["agent_provider"] == "anthropic"

    def test_deployment_fields(self):
        from castor.fria import build_fria_document
        with patch("castor.fria.ConformanceChecker", return_value=self._patched_checker()):
            doc = build_fria_document(
                _make_config(), "safety_component", "indoor nav", prerequisite_waived=True
            )
        assert doc["deployment"]["annex_iii_basis"] == "safety_component"
        assert doc["deployment"]["intended_use"] == "indoor nav"
        assert doc["deployment"]["prerequisite_waived"] is True

    def test_conformance_score_present(self):
        from castor.fria import build_fria_document
        with patch("castor.fria.ConformanceChecker", return_value=self._patched_checker(87)):
            doc = build_fria_document(_make_config(), "safety_component", "indoor nav")
        assert doc["conformance"]["score"] == 87
        assert isinstance(doc["conformance"]["checks"], list)
        assert len(doc["conformance"]["checks"]) == 2

    def test_raises_on_invalid_annex_iii_basis(self):
        from castor.fria import build_fria_document
        with patch("castor.fria.ConformanceChecker", return_value=self._patched_checker()):
            with pytest.raises(ValueError, match="Invalid annex_iii_basis"):
                build_fria_document(_make_config(), "not_a_valid_basis", "indoor nav")

    def test_hardware_observations_empty_when_no_memory(self):
        from castor.fria import build_fria_document
        with patch("castor.fria.ConformanceChecker", return_value=self._patched_checker()):
            doc = build_fria_document(_make_config(), "safety_component", "indoor nav", memory_path=None)
        assert doc["hardware_observations"] == []

    def test_hardware_observations_loaded_from_memory(self, tmp_path):
        """HARDWARE_OBSERVATION entries with confidence >= 0.30 are included."""
        from castor.brain.memory_schema import EntryType, MemoryEntry, RobotMemory, save_memory
        from castor.fria import build_fria_document
        from datetime import datetime

        now = datetime.now()
        memory = RobotMemory(
            schema_version="1.0",
            rrn="RRN-000000000001",
            last_updated=now,
            entries=[
                MemoryEntry(
                    id="mem-abc01",
                    type=EntryType.HARDWARE_OBSERVATION,
                    text="Left motor stalls",
                    confidence=0.82,
                    first_seen=now,
                    last_reinforced=now,
                    tags=["motor"],
                ),
                MemoryEntry(
                    id="mem-abc02",
                    type=EntryType.HARDWARE_OBSERVATION,
                    text="Low confidence obs",
                    confidence=0.10,  # below threshold
                    first_seen=now,
                    last_reinforced=now,
                    tags=[],
                ),
                MemoryEntry(
                    id="mem-abc03",
                    type=EntryType.ENVIRONMENT_NOTE,  # wrong type
                    text="Lab environment",
                    confidence=0.9,
                    first_seen=now,
                    last_reinforced=now,
                    tags=[],
                ),
            ],
        )
        mem_path = str(tmp_path / "robot-memory.md")
        save_memory(memory, mem_path)

        with patch("castor.fria.ConformanceChecker", return_value=self._patched_checker()):
            doc = build_fria_document(
                _make_config(), "safety_component", "indoor nav", memory_path=mem_path
            )
        obs = doc["hardware_observations"]
        assert len(obs) == 1
        assert obs[0]["id"] == "mem-abc01"
        assert obs[0]["text"] == "Left motor stalls"
