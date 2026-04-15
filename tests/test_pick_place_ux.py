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


# ── 2. Firestore task doc helpers ─────────────────────────────────────────────

class TestTaskDocHelpers:
    def test_write_task_doc_creates_document(self):
        bridge = _make_bridge()
        task_ref_mock = MagicMock()
        bridge._robot_ref().collection.return_value.document.return_value = task_ref_mock

        bridge._write_task_doc(
            task_id="abc123",
            target="red lego",
            destination="bowl",
            status="pending_confirmation",
        )

        task_ref_mock.set.assert_called_once()
        call_args = task_ref_mock.set.call_args[0][0]
        assert call_args["task_id"] == "abc123"
        assert call_args["target"] == "red lego"
        assert call_args["destination"] == "bowl"
        assert call_args["status"] == "pending_confirmation"
        assert call_args["type"] == "pick_place"
        assert call_args["confirmed"] is False

    def test_write_task_doc_swallows_firestore_error(self):
        bridge = _make_bridge()
        bridge._robot_ref().collection.return_value.document.return_value.set.side_effect = Exception("timeout")
        # Must not raise
        bridge._write_task_doc("abc", "obj", "dest", "running")

    def test_update_task_doc_does_partial_update(self):
        bridge = _make_bridge()
        task_ref_mock = MagicMock()
        bridge._robot_ref().collection.return_value.document.return_value = task_ref_mock

        bridge._update_task_doc("abc123", {"phase": "APPROACH", "status": "running"})

        task_ref_mock.update.assert_called_once()
        call_args = task_ref_mock.update.call_args[0][0]
        assert call_args["phase"] == "APPROACH"
        assert call_args["status"] == "running"
        assert "updated_at" in call_args

    def test_update_task_doc_swallows_error(self):
        bridge = _make_bridge()
        bridge._robot_ref().collection.return_value.document.return_value.update.side_effect = Exception("boom")
        bridge._update_task_doc("abc", {"status": "failed"})
