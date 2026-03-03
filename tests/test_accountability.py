"""
Unit tests for the AI Decision Accountability Layer (PRD: OpenCastor AI Accountability).

Covers:
  - ConfidenceGateEnforcer: block/escalate/allow/missing confidence/no matching gate
  - ThoughtLog: record and retrieve thoughts
  - AuditLog: ai sub-dict present when thought is passed to log_motor_command
  - gate_bypassed flag propagation
"""

import json
import os
import tempfile

import pytest

from castor.confidence_gate import ConfidenceGate, ConfidenceGateEnforcer, GateOutcome
from castor.providers.base import Thought
from castor.thought_log import ThoughtLog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_thought(**kwargs) -> Thought:
    """Return a Thought with sensible defaults, overridden by kwargs."""
    defaults = dict(
        raw_text="test thought",
        action={"type": "move", "linear": 0.5, "angular": 0.0},
        confidence=0.9,
        provider="test_provider",
        model="test_model",
        layer="fast",
    )
    defaults.update(kwargs)
    return Thought(**defaults)


# ---------------------------------------------------------------------------
# ConfidenceGateEnforcer tests
# ---------------------------------------------------------------------------

class TestConfidenceGateEnforcer:
    """Tests for ConfidenceGateEnforcer.evaluate()."""

    def _enforcer(self, on_fail="block", min_confidence=0.6):
        gates = [ConfidenceGate(scope="control", min_confidence=min_confidence, on_fail=on_fail)]
        return ConfidenceGateEnforcer(gates)

    def test_pass_above_threshold(self):
        enforcer = self._enforcer(on_fail="block", min_confidence=0.6)
        result = enforcer.evaluate("control", 0.8)
        assert result == GateOutcome.PASS

    def test_pass_exact_threshold(self):
        enforcer = self._enforcer(on_fail="block", min_confidence=0.6)
        result = enforcer.evaluate("control", 0.6)
        assert result == GateOutcome.PASS

    def test_block_below_threshold(self):
        enforcer = self._enforcer(on_fail="block", min_confidence=0.6)
        result = enforcer.evaluate("control", 0.4)
        assert result == GateOutcome.BLOCK

    def test_escalate_below_threshold(self):
        enforcer = self._enforcer(on_fail="escalate", min_confidence=0.6)
        result = enforcer.evaluate("control", 0.4)
        assert result == GateOutcome.ESCALATE

    def test_bypass_when_on_fail_allow(self):
        enforcer = self._enforcer(on_fail="allow", min_confidence=0.6)
        result = enforcer.evaluate("control", 0.1)
        assert result == GateOutcome.BYPASS

    def test_missing_confidence_triggers_fail(self):
        """None confidence should trigger on_fail behaviour."""
        enforcer_block = self._enforcer(on_fail="block")
        enforcer_escalate = self._enforcer(on_fail="escalate")
        enforcer_allow = self._enforcer(on_fail="allow")
        assert enforcer_block.evaluate("control", None) == GateOutcome.BLOCK
        assert enforcer_escalate.evaluate("control", None) == GateOutcome.ESCALATE
        assert enforcer_allow.evaluate("control", None) == GateOutcome.BYPASS

    def test_no_matching_gate_returns_pass(self):
        """If no gate is configured for a scope, evaluation is PASS."""
        enforcer = self._enforcer(on_fail="block", min_confidence=0.9)
        result = enforcer.evaluate("unknown_scope", 0.1)
        assert result == GateOutcome.PASS

    def test_empty_gates_always_pass(self):
        enforcer = ConfidenceGateEnforcer([])
        assert enforcer.evaluate("control", 0.0) == GateOutcome.PASS
        assert enforcer.evaluate("control", None) == GateOutcome.PASS

    def test_multiple_scopes_independent(self):
        gates = [
            ConfidenceGate(scope="control", min_confidence=0.7, on_fail="block"),
            ConfidenceGate(scope="nav", min_confidence=0.4, on_fail="escalate"),
        ]
        enforcer = ConfidenceGateEnforcer(gates)
        assert enforcer.evaluate("control", 0.8) == GateOutcome.PASS
        assert enforcer.evaluate("control", 0.5) == GateOutcome.BLOCK
        assert enforcer.evaluate("nav", 0.5) == GateOutcome.PASS
        assert enforcer.evaluate("nav", 0.3) == GateOutcome.ESCALATE


# ---------------------------------------------------------------------------
# ThoughtLog tests
# ---------------------------------------------------------------------------

class TestThoughtLog:
    """Tests for ThoughtLog.record() and ThoughtLog.get()."""

    def test_record_and_get(self):
        log = ThoughtLog()
        t = _make_thought()
        log.record(t)
        result = log.get(t.id)
        assert result is not None
        assert result["id"] == t.id

    def test_get_unknown_id_returns_none(self):
        log = ThoughtLog()
        assert log.get("nonexistent-id-00000") is None

    def test_reasoning_excluded_by_default(self):
        log = ThoughtLog()
        t = _make_thought(raw_text="detailed reasoning content")
        log.record(t)
        result = log.get(t.id)
        assert "reasoning" not in result

    def test_reasoning_included_when_requested(self):
        log = ThoughtLog()
        t = _make_thought(raw_text="detailed reasoning content")
        log.record(t)
        result = log.get(t.id, include_reasoning=True)
        assert result["reasoning"] == "detailed reasoning content"

    def test_metadata_fields_present(self):
        log = ThoughtLog()
        t = _make_thought(provider="anthropic", model="claude-sonnet-4-6", layer="planner")
        log.record(t)
        result = log.get(t.id, include_reasoning=False)
        assert result["provider"] == "anthropic"
        assert result["model"] == "claude-sonnet-4-6"
        assert result["layer"] == "planner"
        assert "timestamp_ms" in result

    def test_maxmemory_evicts_oldest(self):
        log = ThoughtLog(max_memory=3)
        ids = []
        for _ in range(5):
            t = _make_thought()
            log.record(t)
            ids.append(t.id)
        # Oldest two should be evicted
        assert log.get(ids[0]) is None
        assert log.get(ids[1]) is None
        # Newest three should remain
        assert log.get(ids[2]) is not None
        assert log.get(ids[3]) is not None
        assert log.get(ids[4]) is not None

    def test_jsonl_persistence(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            path = f.name
        try:
            log = ThoughtLog(storage_path=path)
            t = _make_thought()
            log.record(t)
            # Verify JSONL file was written
            with open(path) as fh:
                lines = [l.strip() for l in fh if l.strip()]
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert entry["id"] == t.id
        finally:
            os.unlink(path)

    def test_list_recent(self):
        log = ThoughtLog()
        ids = []
        for _ in range(5):
            t = _make_thought()
            log.record(t)
            ids.append(t.id)
        recent = log.list_recent(limit=3)
        assert len(recent) == 3
        assert recent[-1]["id"] == ids[-1]


# ---------------------------------------------------------------------------
# AuditLog.log_motor_command — ai sub-dict tests
# ---------------------------------------------------------------------------

class TestAuditLogMotorCommand:
    """Verify the ai sub-dict is present (and absent) in audit entries."""

    def _read_last_entry(self, log_path: str) -> dict:
        with open(log_path) as f:
            lines = [l.strip() for l in f if l.strip()]
        return json.loads(lines[-1])

    def test_ai_block_present_when_thought_provided(self):
        from castor.audit import AuditLog

        with tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode="w") as f:
            path = f.name
        try:
            audit = AuditLog(log_path=path)
            t = _make_thought(
                provider="anthropic",
                model="claude-sonnet-4-6",
                layer="fast",
                confidence=0.85,
                escalated=False,
            )
            audit.log_motor_command({"type": "move", "linear": 0.5}, thought=t)
            entry = self._read_last_entry(path)
            assert "ai" in entry, "Expected 'ai' sub-dict in audit entry"
            ai = entry["ai"]
            assert ai["provider"] == "anthropic"
            assert ai["model"] == "claude-sonnet-4-6"
            assert ai["layer"] == "fast"
            assert ai["confidence"] == pytest.approx(0.85)
            assert ai["escalated"] is False
            assert ai["thought_id"] == t.id
        finally:
            os.unlink(path)

    def test_ai_block_absent_when_no_thought(self):
        from castor.audit import AuditLog

        with tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode="w") as f:
            path = f.name
        try:
            audit = AuditLog(log_path=path)
            audit.log_motor_command({"type": "stop"})
            entry = self._read_last_entry(path)
            assert "ai" not in entry
        finally:
            os.unlink(path)

    def test_ai_block_escalated_flag(self):
        from castor.audit import AuditLog

        with tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode="w") as f:
            path = f.name
        try:
            audit = AuditLog(log_path=path)
            t = _make_thought(layer="planner", escalated=True)
            audit.log_motor_command({"type": "grip", "state": "open"}, thought=t)
            entry = self._read_last_entry(path)
            assert entry["ai"]["escalated"] is True
            assert entry["ai"]["layer"] == "planner"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# gate_bypassed flag tests
# ---------------------------------------------------------------------------

class TestGateBypassedFlag:
    """Tests for the gate_bypassed field on the Thought dataclass."""

    def test_thought_gate_bypassed_default_false(self):
        t = _make_thought()
        assert t.gate_bypassed is False

    def test_thought_gate_bypassed_can_be_set(self):
        t = _make_thought()
        t.gate_bypassed = True
        assert t.gate_bypassed is True

    def test_bypass_outcome_maps_correctly(self):
        """GateOutcome.BYPASS corresponds to on_fail=allow behaviour."""
        gates = [ConfidenceGate(scope="control", min_confidence=0.9, on_fail="allow")]
        enforcer = ConfidenceGateEnforcer(gates)
        outcome = enforcer.evaluate("control", 0.1)
        assert outcome == GateOutcome.BYPASS
        # Caller should set thought.gate_bypassed = True when BYPASS
        t = _make_thought(confidence=0.1)
        if outcome == GateOutcome.BYPASS:
            t.gate_bypassed = True
        assert t.gate_bypassed is True


# ---------------------------------------------------------------------------
# Thought dataclass — basic field tests
# ---------------------------------------------------------------------------

class TestThoughtDataclass:
    """Verify new fields on the Thought dataclass."""

    def test_default_fields_exist(self):
        t = Thought("hello")
        assert t.raw_text == "hello"
        assert t.action is None
        assert t.confidence == 1.0
        assert t.id is not None and len(t.id) > 0
        assert t.provider == ""
        assert t.model == ""
        assert t.model_version is None
        assert t.layer == "fast"
        assert t.latency_ms is None
        assert t.escalated is False
        assert t.gate_bypassed is False

    def test_unique_ids(self):
        t1 = Thought("a")
        t2 = Thought("b")
        assert t1.id != t2.id

    def test_positional_construction_still_works(self):
        """Existing code uses Thought(raw_text, action) positionally."""
        t = Thought("reactive action", {"type": "stop"})
        assert t.raw_text == "reactive action"
        assert t.action == {"type": "stop"}
