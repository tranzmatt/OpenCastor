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


# ── 3. Wait for confirmation ───────────────────────────────────────────────────

class TestWaitForConfirmation:
    def test_returns_true_when_confirmed_immediately(self):
        bridge = _make_bridge()

        # Simulate: Firestore listener fires immediately with confirmed=True
        def fake_on_snapshot(callback, error_callback=None, snapshot_listener_info=None):
            snap = MagicMock()
            snap.exists = True
            snap.to_dict.return_value = {"confirmed": True, "status": "pending_confirmation"}
            callback([snap], None, None)
            return MagicMock()  # listener handle

        bridge._tasks_ref().document.return_value.on_snapshot = fake_on_snapshot

        result = bridge._wait_for_confirmation("task-abc", timeout_s=5)
        assert result is True

    def test_returns_false_on_timeout(self):
        bridge = _make_bridge()

        # Simulate: listener never fires confirmed
        def fake_on_snapshot(callback, error_callback=None, snapshot_listener_info=None):
            return MagicMock()  # handle, but never fires

        bridge._tasks_ref().document.return_value.on_snapshot = fake_on_snapshot

        result = bridge._wait_for_confirmation("task-xyz", timeout_s=0.1)
        assert result is False

    def test_returns_false_when_confirmed_false(self):
        bridge = _make_bridge()

        def fake_on_snapshot(callback, error_callback=None, snapshot_listener_info=None):
            snap = MagicMock()
            snap.exists = True
            snap.to_dict.return_value = {"confirmed": False}
            callback([snap], None, None)
            return MagicMock()

        bridge._tasks_ref().document.return_value.on_snapshot = fake_on_snapshot

        result = bridge._wait_for_confirmation("task-abc", timeout_s=0.2)
        assert result is False
