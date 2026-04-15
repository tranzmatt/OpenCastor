"""Tests for pick-and-place UX: intent detection, task doc helpers, dispatch."""
from __future__ import annotations

from unittest.mock import MagicMock

from castor.cloud.bridge import CastorBridge, _detect_pick_place_intent

MINIMAL_CONFIG = {
    "rrn": "RRN-00000042",
    "metadata": {"name": "TestBot", "ruri": "rcan://test/bot"},
    "firebase_uid": "uid-test-owner",
    "owner": "rrn://test-owner",
    "task_execution": "ask",
}


def _make_bridge(task_execution: str = "ask") -> CastorBridge:
    cfg = {**MINIMAL_CONFIG, "task_execution": task_execution}
    bridge = CastorBridge(config=cfg, firebase_project="test-project")
    bridge._db = MagicMock()
    bridge._consent = MagicMock()
    bridge._consent.is_authorized.return_value = (True, "ok")
    return bridge


# ── 1. Intent detector ────────────────────────────────────────────────────────

class TestDetectPickPlaceIntent:
    def test_basic_pick_into(self):
        result = _detect_pick_place_intent("pick the red lego brick into the bowl")
        assert result == ("the red lego brick", "the bowl")

    def test_grab_and_place(self):
        result = _detect_pick_place_intent("grab lego and place it into the container")
        assert result == ("lego", "the container")

    def test_take_to(self):
        result = _detect_pick_place_intent("take the cube to the tray")
        assert result == ("the cube", "the tray")

    def test_get_in(self):
        result = _detect_pick_place_intent("get the blue block in the bin")
        assert result == ("the blue block", "the bin")

    def test_no_match_move(self):
        assert _detect_pick_place_intent("move forward") is None

    def test_no_match_chat(self):
        assert _detect_pick_place_intent("what do you see") is None

    def test_no_match_hi(self):
        assert _detect_pick_place_intent("hi") is None

    def test_no_match_status(self):
        assert _detect_pick_place_intent("STATUS") is None
