# Robot Manipulation Task UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire natural-language pick-and-place instructions through the bridge to a live `TaskProgressCard` in the Flutter chat UI, with real-time SCAN → APPROACH → GRASP → PLACE progress and an ask/automatic confirmation toggle.

**Architecture:** Bridge detects pick-and-place intent → creates Firestore task doc → gateway executes `arm_pick_place` writing phase updates → Flutter streams the task doc and renders `TaskProgressCard` inline in chat. A `task_execution: ask | automatic` robot setting controls whether the user must confirm before the arm moves.

**Tech Stack:** Python 3.10+ (bridge, gateway), Firebase Firestore (firebase-admin), Flutter/Dart (Riverpod, cloud_firestore), pytest

---

## File Map

**Python (OpenCastor repo — `/home/craigm26/OpenCastor`)**

| File | Change |
|------|--------|
| `castor/cloud/bridge.py` | Add `_detect_pick_place_intent`, `_write_task_doc`, `_update_task_doc`, `_wait_for_confirmation`, `_dispatch_pick_place`; wire into `_dispatch_to_gateway` |
| `castor/api.py` | Extend `_PickPlaceRequest` with `task_id`/`firebase_project`/`rrn`; add `_write_task_phase` helper; write phase updates in `arm_pick_place` |
| `tests/test_pick_place_ux.py` | New test file — all Python tests for this feature |

**Flutter (opencastor-client repo — `/home/craigm26/opencastor-client`)**

| File | Change |
|------|--------|
| `lib/data/models/task_doc.dart` | New — `TaskDoc` model with `fromFirestore` factory |
| `lib/data/models/command.dart` | Add optional `taskId` field to `RobotCommand` + `fromDoc` |
| `lib/data/repositories/robot_repository.dart` | Add `watchTask` + `confirmTask` abstract methods |
| `lib/data/services/firestore_robot_service.dart` | Implement `watchTask` + `confirmTask` with direct Firestore write |
| `lib/ui/robot_detail/robot_detail_view_model.dart` | Add `taskDocProvider` + `confirmTaskNotifier` |
| `lib/ui/widgets/task_progress_card.dart` | New — `TaskProgressCard` widget |
| `lib/ui/robot_detail/robot_detail_screen.dart` | Route commands with `taskId` to `TaskProgressCard` in list |
| `lib/ui/robot_capabilities/robot_capabilities_screen.dart` | Add `task_execution` toggle in settings section |
| `test/task_progress_card_test.dart` | New — widget tests for `TaskProgressCard` |

---

## Task 1: Bridge Intent Detector

**Files:**
- Modify: `castor/cloud/bridge.py` (add module-level function `_detect_pick_place_intent`)
- Test: `tests/test_pick_place_ux.py` (create new file)

Context: `bridge.py` has 2210 lines. The function goes above the `CastorBridge` class (before line 268). The test file follows the pattern from `tests/test_v15_bridge.py`.

- [ ] **Step 1: Create the test file with failing tests**

Create `/home/craigm26/OpenCastor/tests/test_pick_place_ux.py`:

```python
"""Tests for pick-and-place UX: intent detection, task doc helpers, dispatch."""
from __future__ import annotations

import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

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
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /home/craigm26/OpenCastor
pytest tests/test_pick_place_ux.py::TestDetectPickPlaceIntent -v 2>&1 | head -30
```

Expected: `ImportError: cannot import name '_detect_pick_place_intent'`

- [ ] **Step 3: Add `_detect_pick_place_intent` to `bridge.py`**

Add this block immediately before the `class CastorBridge:` line (line ~268 in bridge.py):

```python
# ---------------------------------------------------------------------------
# Pick-and-place intent detection
# ---------------------------------------------------------------------------

import re as _re

_PICK_PLACE_RE = _re.compile(
    r"(?:pick|grab|take|get)\s+(?P<target>.+?)\s+"
    r"(?:into|in\b|to\b|onto\b|and\s+place\s+(?:it\s+)?(?:into|in))\s+"
    r"(?P<destination>.+)",
    _re.IGNORECASE,
)


def _detect_pick_place_intent(instruction: str) -> tuple[str, str] | None:
    """Return (target, destination) if instruction is a pick-and-place, else None.

    Examples::
        "pick the red lego into the bowl"  → ("the red lego", "the bowl")
        "grab cube and place it into tray" → ("cube", "tray")
        "move forward"                     → None
    """
    m = _PICK_PLACE_RE.search(instruction.strip())
    if m:
        return m.group("target").strip(), m.group("destination").strip()
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/craigm26/OpenCastor
pytest tests/test_pick_place_ux.py::TestDetectPickPlaceIntent -v
```

Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/craigm26/OpenCastor
git add castor/cloud/bridge.py tests/test_pick_place_ux.py
git commit -m "feat(bridge): add pick-and-place intent detector"
```

---

## Task 2: Bridge Firestore Task Doc Helpers

**Files:**
- Modify: `castor/cloud/bridge.py` (add `_write_task_doc`, `_update_task_doc` to `CastorBridge`)
- Test: `tests/test_pick_place_ux.py` (append `TestTaskDocHelpers`)

Context: `_write_task_doc` creates the initial task document at `robots/{rrn}/tasks/{task_id}`. `_update_task_doc` does a partial update. Both are best-effort (swallow exceptions).

- [ ] **Step 1: Add failing tests — append to `tests/test_pick_place_ux.py`**

```python
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /home/craigm26/OpenCastor
pytest tests/test_pick_place_ux.py::TestTaskDocHelpers -v 2>&1 | head -20
```

Expected: `AttributeError: 'CastorBridge' object has no attribute '_write_task_doc'`

- [ ] **Step 3: Add the methods to `CastorBridge`**

Add after the `_write_mission_response` method (around line 1638 in bridge.py). Look for the line `def _build_mission_context` and add before it:

```python
    # ------------------------------------------------------------------
    # Pick-and-place task doc helpers
    # ------------------------------------------------------------------

    def _tasks_ref(self) -> Any:
        return self._robot_ref().collection("tasks")

    def _write_task_doc(
        self,
        task_id: str,
        target: str,
        destination: str,
        status: str,
    ) -> None:
        """Create the initial task document in Firestore. Best-effort — never raises."""
        if not self._db:
            return
        try:
            now = datetime.now(timezone.utc).isoformat()
            self._tasks_ref().document(task_id).set(
                {
                    "task_id": task_id,
                    "type": "pick_place",
                    "target": target,
                    "destination": destination,
                    "status": status,
                    "phase": "SCAN",
                    "detected_objects": [],
                    "frame_b64": None,
                    "error": None,
                    "confirmed": False,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        except Exception as exc:
            log.warning("_write_task_doc failed (task_id=%s): %s", task_id, exc)

    def _update_task_doc(self, task_id: str, fields: dict[str, Any]) -> None:
        """Partial update to a task document. Best-effort — never raises."""
        if not self._db:
            return
        try:
            fields["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._tasks_ref().document(task_id).update(fields)
        except Exception as exc:
            log.warning("_update_task_doc failed (task_id=%s): %s", task_id, exc)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/craigm26/OpenCastor
pytest tests/test_pick_place_ux.py::TestTaskDocHelpers -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/craigm26/OpenCastor
git add castor/cloud/bridge.py tests/test_pick_place_ux.py
git commit -m "feat(bridge): add Firestore task doc helpers for pick-and-place"
```

---

## Task 3: Bridge `_wait_for_confirmation`

**Files:**
- Modify: `castor/cloud/bridge.py` (add `_wait_for_confirmation` to `CastorBridge`)
- Test: `tests/test_pick_place_ux.py` (append `TestWaitForConfirmation`)

Context: Uses a `threading.Event` + Firestore `on_snapshot` listener. The listener sets the event when `confirmed == True`. Returns `True` if confirmed within timeout, `False` on timeout. The listener is detached after returning.

- [ ] **Step 1: Add failing tests — append to `tests/test_pick_place_ux.py`**

```python
# ── 3. Wait for confirmation ───────────────────────────────────────────────────

class TestWaitForConfirmation:
    def test_returns_true_when_confirmed_immediately(self):
        bridge = _make_bridge()

        # Simulate: Firestore listener fires immediately with confirmed=True
        def fake_on_snapshot(callback, error_callback=None, snapshot_listener_info=None):
            # Call callback synchronously with a mock snapshot
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /home/craigm26/OpenCastor
pytest tests/test_pick_place_ux.py::TestWaitForConfirmation -v 2>&1 | head -15
```

Expected: `AttributeError: '_wait_for_confirmation'`

- [ ] **Step 3: Add `_wait_for_confirmation` to `CastorBridge`**

Add immediately after `_update_task_doc` (still inside `CastorBridge`):

```python
    def _wait_for_confirmation(self, task_id: str, timeout_s: float = 120.0) -> bool:
        """Wait for the Flutter app to set confirmed=True on the task doc.

        Uses a Firestore on_snapshot listener (no polling). Returns True if
        confirmed within timeout_s, False otherwise. Always detaches the listener.
        """
        if not self._db:
            return False

        confirmed_event = threading.Event()

        def _on_snapshot(doc_snapshots, changes, read_time) -> None:
            for snap in doc_snapshots:
                if snap.exists and snap.to_dict().get("confirmed") is True:
                    confirmed_event.set()

        task_ref = self._tasks_ref().document(task_id)
        listener = task_ref.on_snapshot(_on_snapshot)
        try:
            return confirmed_event.wait(timeout=timeout_s)
        finally:
            try:
                listener.unsubscribe()
            except Exception:
                pass
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/craigm26/OpenCastor
pytest tests/test_pick_place_ux.py::TestWaitForConfirmation -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/craigm26/OpenCastor
git add castor/cloud/bridge.py tests/test_pick_place_ux.py
git commit -m "feat(bridge): add _wait_for_confirmation with Firestore listener"
```

---

## Task 4: Bridge `_dispatch_pick_place` + routing

**Files:**
- Modify: `castor/cloud/bridge.py` (add `_dispatch_pick_place`; wire into `_dispatch_to_gateway`)
- Test: `tests/test_pick_place_ux.py` (append `TestDispatchPickPlace`)

Context: `_dispatch_to_gateway` is at line ~1641. The chat/control branch is at line ~1809. We add an intent check BEFORE the `if scope == "status":` block. `_dispatch_pick_place` reads `task_execution` from `self._rcan_config`, creates task doc, optionally waits for confirmation, then calls the gateway `POST /api/arm/pick_place`.

- [ ] **Step 1: Add failing tests — append to `tests/test_pick_place_ux.py`**

```python
# ── 4. _dispatch_pick_place ───────────────────────────────────────────────────

class TestDispatchPickPlace:
    def test_routes_pick_intent_to_pick_place_endpoint(self):
        bridge = _make_bridge(task_execution="automatic")

        with patch("httpx.Client") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"status": "complete", "log": []}
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.raise_for_status = MagicMock()
            mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

            doc = {"scope": "chat", "instruction": "pick lego into bowl",
                   "issued_at": time.time(), "sender_type": "human"}
            result = bridge._dispatch_to_gateway("chat", "pick lego into bowl", doc)

        # Should have called /api/arm/pick_place, not /api/command
        call_args = mock_client_cls.return_value.__enter__.return_value.post.call_args
        assert "/api/arm/pick_place" in call_args[0][0]
        body = call_args[1]["json"]
        assert body["target"] == "lego"
        assert body["destination"] == "bowl"

    def test_non_pick_intent_routes_to_api_command(self):
        bridge = _make_bridge(task_execution="automatic")

        with patch("httpx.Client") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"raw_text": "hello"}
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.raise_for_status = MagicMock()
            mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

            doc = {"scope": "chat", "instruction": "what do you see",
                   "issued_at": time.time(), "sender_type": "human"}
            bridge._dispatch_to_gateway("chat", "what do you see", doc)

        call_args = mock_client_cls.return_value.__enter__.return_value.post.call_args
        assert "/api/command" in call_args[0][0]

    def test_ask_mode_cancels_on_timeout(self):
        bridge = _make_bridge(task_execution="ask")

        # _wait_for_confirmation returns False (timeout)
        with patch.object(bridge, "_wait_for_confirmation", return_value=False):
            with patch.object(bridge, "_write_task_doc"):
                with patch.object(bridge, "_update_task_doc") as mock_update:
                    doc = {"scope": "chat", "instruction": "pick lego into bowl",
                           "issued_at": time.time(), "sender_type": "human"}
                    result = bridge._dispatch_to_gateway("chat", "pick lego into bowl", doc)

        assert result.get("status") == "cancelled"
        # Must update task doc to cancelled
        update_calls = [c[0][1] for c in mock_update.call_args_list]
        assert any(d.get("status") == "cancelled" for d in update_calls)
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /home/craigm26/OpenCastor
pytest tests/test_pick_place_ux.py::TestDispatchPickPlace -v 2>&1 | head -20
```

Expected: FAIL (no routing yet, pick intent goes to `/api/command`)

- [ ] **Step 3: Add `_dispatch_pick_place` to `CastorBridge`**

Add after `_wait_for_confirmation` (still inside `CastorBridge`):

```python
    def _dispatch_pick_place(
        self,
        target: str,
        destination: str,
        doc: dict[str, Any],
    ) -> dict[str, Any]:
        """Route a pick-and-place instruction to /api/arm/pick_place.

        Creates a Firestore task doc, optionally waits for user confirmation
        (ask mode), then calls the gateway endpoint and returns its result.
        """
        import httpx

        task_id = str(uuid.uuid4())[:8]
        task_execution = self._rcan_config.get("task_execution", "ask")

        initial_status = "pending_confirmation" if task_execution == "ask" else "running"
        self._write_task_doc(task_id, target, destination, initial_status)

        # Attach task_id to the command doc so Flutter can link to it
        if self._db:
            cmd_id = doc.get("cmd_id", "")
            if cmd_id:
                try:
                    self._commands_ref().document(cmd_id).update({"task_id": task_id})
                except Exception:
                    pass

        if task_execution == "ask":
            confirmed = self._wait_for_confirmation(task_id, timeout_s=120.0)
            if not confirmed:
                self._update_task_doc(task_id, {
                    "status": "cancelled",
                    "error": "user_timeout",
                })
                return {"status": "cancelled", "task_id": task_id}
            self._update_task_doc(task_id, {"status": "running"})

        headers = self._auth_headers()
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(
                    f"{self.gateway_url}/api/arm/pick_place",
                    json={
                        "target": target,
                        "destination": destination,
                        "task_id": task_id,
                        "firebase_project": self.firebase_project,
                        "rrn": self.rrn,
                    },
                    headers=headers,
                )
            resp.raise_for_status()
            ct = resp.headers.get("content-type", "")
            result = resp.json() if "application/json" in ct else {"raw": resp.text}
            self._update_task_doc(task_id, {"status": "complete", "phase": "PLACE"})
            return result
        except Exception as exc:
            self._update_task_doc(task_id, {"status": "failed", "error": str(exc)})
            raise
```

- [ ] **Step 4: Wire intent detection into `_dispatch_to_gateway`**

Find the line `elif scope in ("chat", "control"):` in `_dispatch_to_gateway` (~line 1809). Add the following block BEFORE it (after the `elif scope == "system":` block ends):

```python
        # Pick-and-place intent: route to /api/arm/pick_place instead of /api/command
        elif scope in ("chat", "control"):
            pick_place = _detect_pick_place_intent(instruction)
            if pick_place:
                target, destination = pick_place
                return self._dispatch_pick_place(target, destination, doc)
            payload: dict[str, Any] = {
```

**Important**: This replaces the existing `elif scope in ("chat", "control"):` line. The full replacement block is:

```python
        elif scope in ("chat", "control"):
            pick_place = _detect_pick_place_intent(instruction)
            if pick_place:
                target, destination = pick_place
                return self._dispatch_pick_place(target, destination, doc)
            payload: dict[str, Any] = {
                "instruction": instruction,
                "channel": "opencastor_app",
                "context": "opencastor_fleet_ui",
            }
            # Mission thread: inject system context for multi-robot coordination
            if mission_context:
                payload["system_context"] = mission_context
            # v1.6 GAP-18: pass media_chunks as context for vision-capable providers
            if media_chunks:
                payload["media_chunks"] = media_chunks
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    f"{self.gateway_url}/api/command",
                    json=payload,
                    headers=headers,
                )
```

- [ ] **Step 5: Run all bridge pick-place tests**

```bash
cd /home/craigm26/OpenCastor
pytest tests/test_pick_place_ux.py -v
```

Expected: All tests PASS

- [ ] **Step 6: Run existing bridge tests to check for regressions**

```bash
cd /home/craigm26/OpenCastor
pytest tests/test_v15_bridge.py tests/test_v16_bridge.py tests/test_bridge.py -v 2>&1 | tail -10
```

Expected: All existing tests PASS

- [ ] **Step 7: Commit**

```bash
cd /home/craigm26/OpenCastor
git add castor/cloud/bridge.py tests/test_pick_place_ux.py
git commit -m "feat(bridge): route pick-and-place intent to arm_pick_place with task doc"
```

---

## Task 5: Gateway Phase Progress Writes

**Files:**
- Modify: `castor/api.py` (extend `_PickPlaceRequest`, add `_write_task_phase`, update `arm_pick_place`)
- Test: `tests/test_pick_place_ux.py` (append `TestGatewayPhaseWrites`)

Context: The gateway already uses firebase-admin lazily (see lines 1515–1533 for the pattern). The task doc at `robots/{rrn}/tasks/{task_id}` was created by the bridge; the gateway only calls `.update()` on it. `_write_task_phase` is module-level and best-effort.

- [ ] **Step 1: Add failing tests — append to `tests/test_pick_place_ux.py`**

```python
# ── 5. Gateway phase writes ───────────────────────────────────────────────────

from castor.api import _write_task_phase


class TestGatewayPhaseWrites:
    def test_write_task_phase_calls_firestore_update(self):
        mock_db = MagicMock()
        task_ref = MagicMock()
        mock_db.collection.return_value.document.return_value \
            .collection.return_value.document.return_value = task_ref

        _write_task_phase(mock_db, "RRN-001", "task-abc", "APPROACH", "running")

        task_ref.update.assert_called_once()
        call_args = task_ref.update.call_args[0][0]
        assert call_args["phase"] == "APPROACH"
        assert call_args["status"] == "running"

    def test_write_task_phase_swallows_error(self):
        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value \
            .collection.return_value.document.return_value \
            .update.side_effect = Exception("network timeout")
        # Must not raise
        _write_task_phase(mock_db, "RRN-001", "task-abc", "GRASP", "running")

    def test_write_task_phase_no_op_when_no_task_id(self):
        mock_db = MagicMock()
        _write_task_phase(mock_db, "RRN-001", None, "APPROACH", "running")
        mock_db.collection.assert_not_called()
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /home/craigm26/OpenCastor
pytest tests/test_pick_place_ux.py::TestGatewayPhaseWrites -v 2>&1 | head -15
```

Expected: `ImportError: cannot import name '_write_task_phase' from 'castor.api'`

- [ ] **Step 3: Add `_write_task_phase` to `castor/api.py`**

Find the comment `# Vision-guided arm pick-and-place endpoint` (line ~2805) and add before it:

```python
def _write_task_phase(
    db: Any,
    rrn: str,
    task_id: Optional[str],
    phase: str,
    status: str,
    **extra_fields: Any,
) -> None:
    """Best-effort write of a task phase update to Firestore.

    Never raises — Firestore errors are logged and swallowed so arm execution
    continues regardless of telemetry connectivity.
    """
    if db is None or not task_id:
        return
    try:
        from datetime import datetime, timezone as _tz
        fields: dict[str, Any] = {
            "phase": phase,
            "status": status,
            "updated_at": datetime.now(_tz.utc).isoformat(),
            **extra_fields,
        }
        db.collection("robots").document(rrn).collection("tasks").document(task_id).update(fields)
    except Exception as exc:
        logger.warning("_write_task_phase failed (task_id=%s phase=%s): %s", task_id, phase, exc)
```

- [ ] **Step 4: Extend `_PickPlaceRequest` with new fields**

Find `class _PickPlaceRequest(BaseModel):` (line ~2809) and replace it:

```python
class _PickPlaceRequest(BaseModel):
    target: str = "red lego brick"
    destination: str = "bowl"
    max_vision_steps: int = 4
    task_id: Optional[str] = None          # Firestore task doc to write progress to
    firebase_project: Optional[str] = None  # Firebase project for task doc writes
    rrn: Optional[str] = None              # Robot RRN for Firestore path
```

- [ ] **Step 5: Add Firestore client init + phase writes to `arm_pick_place`**

Find the beginning of the `arm_pick_place` function body (after the `503` checks). Add Firestore client init and SCAN write:

```python
    # ── Firestore task progress (best-effort) ─────────────────────────────────
    _task_db: Any = None
    if req.task_id and req.firebase_project and req.rrn:
        try:
            import firebase_admin
            from firebase_admin import credentials as _fb_creds
            from firebase_admin import firestore as _fb_store

            if not firebase_admin._apps:
                cred = _fb_creds.ApplicationDefault()
                firebase_admin.initialize_app(cred)
            _task_db = _fb_store.client()
        except Exception as _exc:
            logger.warning("arm_pick_place: Firestore init failed: %s", _exc)

    # SCAN phase: write initial detection results
    _write_task_phase(_task_db, req.rrn or "", req.task_id, "SCAN", "running")
```

Then, immediately before each `await asyncio.to_thread(_exec, approach)` call, add phase updates:

**Before APPROACH exec** (find `if approach:` block, add before the `await`):
```python
    if approach:
        _write_task_phase(_task_db, req.rrn or "", req.task_id, "APPROACH", "running")
        await asyncio.to_thread(_exec, approach)
        log.append({"phase": "APPROACH", "executed": True})
        _write_task_phase(_task_db, req.rrn or "", req.task_id, "APPROACH", "complete")
```

**Before GRASP exec** (replace existing `if grasp:` block):
```python
    if grasp:
        _write_task_phase(_task_db, req.rrn or "", req.task_id, "GRASP", "running")
        await asyncio.to_thread(_exec, grasp)
        log.append({"phase": "GRASP", "executed": True})
        _write_task_phase(_task_db, req.rrn or "", req.task_id, "GRASP", "complete")
```

**Before PLACE exec** (replace existing `if place:` block):
```python
    if place:
        _write_task_phase(_task_db, req.rrn or "", req.task_id, "PLACE", "running")
        await asyncio.to_thread(_exec, place)
        log.append({"phase": "PLACE", "executed": True})
        _write_task_phase(_task_db, req.rrn or "", req.task_id, "PLACE", "complete")
```

- [ ] **Step 6: Run gateway phase write tests**

```bash
cd /home/craigm26/OpenCastor
pytest tests/test_pick_place_ux.py::TestGatewayPhaseWrites -v
```

Expected: 3 tests PASS

- [ ] **Step 7: Run all pick-place tests + confirm no regressions**

```bash
cd /home/craigm26/OpenCastor
pytest tests/test_pick_place_ux.py -v
ruff check castor/cloud/bridge.py castor/api.py
```

Expected: All PASS, no lint errors

- [ ] **Step 8: Commit**

```bash
cd /home/craigm26/OpenCastor
git add castor/api.py tests/test_pick_place_ux.py
git commit -m "feat(gateway): write task phase progress to Firestore in arm_pick_place"
```

---

## Task 6: Flutter TaskDoc model + Repository methods

**Files:**
- Create: `lib/data/models/task_doc.dart`
- Modify: `lib/data/models/command.dart` (add `taskId`)
- Modify: `lib/data/repositories/robot_repository.dart` (add `watchTask`, `confirmTask`)
- Modify: `lib/data/services/firestore_robot_service.dart` (implement both)
- Test: `test/task_progress_card_test.dart` (create with model test)

Working directory for Flutter steps: `/home/craigm26/opencastor-client`

- [ ] **Step 1: Create failing test**

Create `test/task_progress_card_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:opencastor_client/data/models/task_doc.dart';

void main() {
  group('TaskDoc.fromMap', () {
    test('parses all fields', () {
      final doc = TaskDoc.fromMap('task-abc', {
        'type': 'pick_place',
        'target': 'red lego',
        'destination': 'bowl',
        'status': 'running',
        'phase': 'APPROACH',
        'frame_b64': 'abc123',
        'detected_objects': ['red lego', 'bowl'],
        'error': null,
        'confirmed': false,
        'created_at': '2026-04-14T12:00:00Z',
        'updated_at': '2026-04-14T12:00:01Z',
      });

      expect(doc.taskId, equals('task-abc'));
      expect(doc.target, equals('red lego'));
      expect(doc.destination, equals('bowl'));
      expect(doc.status, equals('running'));
      expect(doc.phase, equals('APPROACH'));
      expect(doc.frameB64, equals('abc123'));
      expect(doc.detectedObjects, equals(['red lego', 'bowl']));
      expect(doc.confirmed, isFalse);
    });

    test('handles missing optional fields', () {
      final doc = TaskDoc.fromMap('task-xyz', {
        'type': 'pick_place',
        'target': 'cube',
        'destination': 'tray',
        'status': 'pending_confirmation',
        'phase': 'SCAN',
      });

      expect(doc.frameB64, isNull);
      expect(doc.detectedObjects, isEmpty);
      expect(doc.confirmed, isFalse);
      expect(doc.error, isNull);
    });
  });
}
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /home/craigm26/opencastor-client
flutter test test/task_progress_card_test.dart 2>&1 | head -20
```

Expected: `Error: Cannot find 'task_doc.dart'`

- [ ] **Step 3: Create `lib/data/models/task_doc.dart`**

```dart
/// TaskDoc — live task progress document from Firestore.
///
/// Streamed from `robots/{rrn}/tasks/{taskId}`.
/// Status values: pending_confirmation | running | complete | failed | cancelled
/// Phase values: SCAN | APPROACH | GRASP | PLACE
library;

class TaskDoc {
  final String taskId;
  final String type;
  final String target;
  final String destination;
  final String status;
  final String phase;
  final String? frameB64;
  final List<String> detectedObjects;
  final String? error;
  final bool confirmed;

  const TaskDoc({
    required this.taskId,
    required this.type,
    required this.target,
    required this.destination,
    required this.status,
    required this.phase,
    this.frameB64,
    required this.detectedObjects,
    this.error,
    required this.confirmed,
  });

  factory TaskDoc.fromMap(String id, Map<String, dynamic> m) {
    return TaskDoc(
      taskId: id,
      type: m['type'] as String? ?? 'pick_place',
      target: m['target'] as String? ?? '',
      destination: m['destination'] as String? ?? '',
      status: m['status'] as String? ?? 'pending_confirmation',
      phase: m['phase'] as String? ?? 'SCAN',
      frameB64: m['frame_b64'] as String?,
      detectedObjects: (m['detected_objects'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      error: m['error'] as String?,
      confirmed: m['confirmed'] as bool? ?? false,
    );
  }

  bool get isPendingConfirmation => status == 'pending_confirmation';
  bool get isRunning => status == 'running';
  bool get isComplete => status == 'complete';
  bool get isFailed => status == 'failed' || status == 'cancelled';
}
```

- [ ] **Step 4: Run test to verify model passes**

```bash
cd /home/craigm26/opencastor-client
flutter test test/task_progress_card_test.dart 2>&1 | tail -5
```

Expected: All tests PASS

- [ ] **Step 5: Add `taskId` to `RobotCommand` in `lib/data/models/command.dart`**

In `command.dart`, add `taskId` field:

```dart
  /// Links this command to a live Firestore task doc for pick-and-place tasks.
  final String? taskId;
```

Add to constructor:
```dart
    this.taskId,
```

Add to `fromDoc` factory (after `senderType` line):
```dart
      taskId: m['task_id'] as String?,
```

- [ ] **Step 6: Add `watchTask` and `confirmTask` to `RobotRepository`**

In `lib/data/repositories/robot_repository.dart`, add after `watchAlerts`:

```dart
  // ── Tasks ──────────────────────────────────────────────────────────────────

  /// Live stream of a pick-and-place task doc.
  Stream<TaskDoc?> watchTask(String rrn, String taskId);

  /// Confirm a pending task — writes confirmed=true to Firestore.
  Future<void> confirmTask(String rrn, String taskId);
```

Add import at top of file:
```dart
import 'task_doc.dart';
```

- [ ] **Step 7: Implement in `FirestoreRobotService`**

In `lib/data/services/firestore_robot_service.dart`, add imports at top:
```dart
import '../models/task_doc.dart';
```

Add after `watchAlerts`:
```dart
  @override
  Stream<TaskDoc?> watchTask(String rrn, String taskId) {
    return _db
        .collection('robots')
        .doc(rrn)
        .collection('tasks')
        .doc(taskId)
        .snapshots()
        .map((snap) {
      if (!snap.exists) return null;
      return TaskDoc.fromMap(snap.id, snap.data() as Map<String, dynamic>);
    });
  }

  @override
  Future<void> confirmTask(String rrn, String taskId) {
    return _db
        .collection('robots')
        .doc(rrn)
        .collection('tasks')
        .doc(taskId)
        .update({'confirmed': true, 'status': 'running'});
  }
```

- [ ] **Step 8: Verify Flutter analyzes cleanly**

```bash
cd /home/craigm26/opencastor-client
flutter analyze lib/data/ 2>&1 | tail -10
```

Expected: No errors

- [ ] **Step 9: Commit**

```bash
cd /home/craigm26/opencastor-client
git add lib/data/models/task_doc.dart lib/data/models/command.dart \
        lib/data/repositories/robot_repository.dart \
        lib/data/services/firestore_robot_service.dart \
        test/task_progress_card_test.dart
git commit -m "feat(flutter): add TaskDoc model, watchTask/confirmTask repository methods"
```

---

## Task 7: Flutter Providers

**Files:**
- Modify: `lib/ui/robot_detail/robot_detail_view_model.dart` (add `taskDocProvider`, `confirmTaskNotifier`)

Context: Follow the existing provider pattern. `taskDocProvider` is a `StreamProvider.family<TaskDoc?, ({String rrn, String taskId})>`. `confirmTaskNotifier` is a simple `AutoDisposeAsyncNotifier` that calls `repo.confirmTask`.

- [ ] **Step 1: Add providers to `robot_detail_view_model.dart`**

At the bottom of `lib/ui/robot_detail/robot_detail_view_model.dart`, add:

```dart
import '../../data/models/task_doc.dart';

// ── Task doc provider ─────────────────────────────────────────────────────────

/// Live stream of a pick-and-place task doc.
///
/// Usage: `ref.watch(taskDocProvider((rrn: rrn, taskId: taskId)))`
final taskDocProvider = StreamProvider.autoDispose
    .family<TaskDoc?, ({String rrn, String taskId})>((ref, args) {
  return ref
      .read(robotRepositoryProvider)
      .watchTask(args.rrn, args.taskId);
});

// ── Confirm task notifier ─────────────────────────────────────────────────────

/// Confirms a pending pick-and-place task.
///
/// Usage: `ref.read(confirmTaskProvider.notifier).confirm(rrn: rrn, taskId: id)`
final confirmTaskProvider =
    AsyncNotifierProvider.autoDispose<ConfirmTaskNotifier, void>(
  ConfirmTaskNotifier.new,
);

class ConfirmTaskNotifier extends AutoDisposeAsyncNotifier<void> {
  @override
  Future<void> build() async {}

  Future<void> confirm({required String rrn, required String taskId}) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() =>
        ref.read(robotRepositoryProvider).confirmTask(rrn, taskId));
  }
}
```

- [ ] **Step 2: Verify analyzers cleanly**

```bash
cd /home/craigm26/opencastor-client
flutter analyze lib/ui/robot_detail/robot_detail_view_model.dart 2>&1 | tail -5
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /home/craigm26/opencastor-client
git add lib/ui/robot_detail/robot_detail_view_model.dart
git commit -m "feat(flutter): add taskDocProvider and ConfirmTaskNotifier"
```

---

## Task 8: Flutter TaskProgressCard + Chat Routing

**Files:**
- Create: `lib/ui/widgets/task_progress_card.dart`
- Modify: `lib/ui/robot_detail/robot_detail_screen.dart` (route taskId commands)
- Test: `test/task_progress_card_test.dart` (append widget tests)

Context: The card renders inline in the chat list. It watches `taskDocProvider`. The `[Run ▶]` button calls `confirmTaskProvider`. The chat list in `robot_detail_screen.dart` currently calls `ChatBubble` for every command — we insert a check before that.

- [ ] **Step 1: Add widget tests — append to `test/task_progress_card_test.dart`**

```dart
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:opencastor_client/data/models/task_doc.dart';
import 'package:opencastor_client/ui/widgets/task_progress_card.dart';
import 'package:opencastor_client/ui/robot_detail/robot_detail_view_model.dart';

// Helper to build widget under test with a mocked taskDocProvider
Widget _buildCard({
  required TaskDoc? taskDoc,
  String rrn = 'RRN-001',
  String taskId = 'task-abc',
  VoidCallback? onConfirm,
}) {
  return ProviderScope(
    overrides: [
      taskDocProvider.overrideWith((ref, args) => Stream.value(taskDoc)),
      confirmTaskProvider.overrideWith((_) => _FakeConfirmNotifier()),
    ],
    child: MaterialApp(
      home: Scaffold(
        body: TaskProgressCard(rrn: rrn, taskId: taskId),
      ),
    ),
  );
}

class _FakeConfirmNotifier extends AutoDisposeAsyncNotifier<void> {
  @override
  Future<void> build() async {}
  Future<void> confirm({required String rrn, required String taskId}) async {}
}

group('TaskProgressCard', () {
  testWidgets('shows Run button when pending_confirmation', (tester) async {
    final doc = TaskDoc.fromMap('task-abc', {
      'type': 'pick_place', 'target': 'lego', 'destination': 'bowl',
      'status': 'pending_confirmation', 'phase': 'SCAN',
    });
    await tester.pumpWidget(_buildCard(taskDoc: doc));
    await tester.pump();
    expect(find.text('Run ▶'), findsOneWidget);
  });

  testWidgets('hides Run button when running', (tester) async {
    final doc = TaskDoc.fromMap('task-abc', {
      'type': 'pick_place', 'target': 'lego', 'destination': 'bowl',
      'status': 'running', 'phase': 'APPROACH',
    });
    await tester.pumpWidget(_buildCard(taskDoc: doc));
    await tester.pump();
    expect(find.text('Run ▶'), findsNothing);
  });

  testWidgets('shows all 4 phase labels', (tester) async {
    final doc = TaskDoc.fromMap('task-abc', {
      'type': 'pick_place', 'target': 'lego', 'destination': 'bowl',
      'status': 'running', 'phase': 'APPROACH',
    });
    await tester.pumpWidget(_buildCard(taskDoc: doc));
    await tester.pump();
    for (final phase in ['SCAN', 'APPROACH', 'GRASP', 'PLACE']) {
      expect(find.text(phase), findsOneWidget);
    }
  });

  testWidgets('shows target and destination', (tester) async {
    final doc = TaskDoc.fromMap('task-abc', {
      'type': 'pick_place', 'target': 'red lego', 'destination': 'bowl',
      'status': 'pending_confirmation', 'phase': 'SCAN',
    });
    await tester.pumpWidget(_buildCard(taskDoc: doc));
    await tester.pump();
    expect(find.textContaining('red lego'), findsOneWidget);
    expect(find.textContaining('bowl'), findsOneWidget);
  });
});
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /home/craigm26/opencastor-client
flutter test test/task_progress_card_test.dart 2>&1 | head -20
```

Expected: `Error: Cannot find 'task_progress_card.dart'`

- [ ] **Step 3: Create `lib/ui/widgets/task_progress_card.dart`**

```dart
/// TaskProgressCard — renders pick-and-place task progress inline in chat.
///
/// Streams live updates from `robots/{rrn}/tasks/{taskId}` via Firestore.
/// Shows phase chips (SCAN → APPROACH → GRASP → PLACE) with state indicators,
/// a scene snapshot if available, and a [Run ▶] button in ask mode.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models/task_doc.dart';
import '../robot_detail/robot_detail_view_model.dart';
import '../core/theme/app_theme.dart';

const _kPhases = ['SCAN', 'APPROACH', 'GRASP', 'PLACE'];

class TaskProgressCard extends ConsumerWidget {
  final String rrn;
  final String taskId;

  const TaskProgressCard({super.key, required this.rrn, required this.taskId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final taskAsync = ref.watch(taskDocProvider((rrn: rrn, taskId: taskId)));
    final cs = Theme.of(context).colorScheme;

    return taskAsync.when(
      loading: () => const SizedBox(height: 48, child: Center(child: CircularProgressIndicator(strokeWidth: 2))),
      error: (e, _) => _errorCard(context, e.toString()),
      data: (task) {
        if (task == null) return const SizedBox.shrink();
        return _TaskCard(rrn: rrn, task: task);
      },
    );
  }

  Widget _errorCard(BuildContext context, String err) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Text('Task error: $err',
            style: TextStyle(color: Theme.of(context).colorScheme.error)),
      ),
    );
  }
}

class _TaskCard extends ConsumerWidget {
  final String rrn;
  final TaskDoc task;
  const _TaskCard({required this.rrn, required this.task});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // ── Header ────────────────────────────────────────────────────
            Row(
              children: [
                const Icon(Icons.precision_manufacturing_outlined, size: 18),
                const SizedBox(width: 6),
                Text('Pick & Place',
                    style: theme.textTheme.titleSmall
                        ?.copyWith(fontWeight: FontWeight.bold)),
                const Spacer(),
                _StatusChip(status: task.status),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              '${task.target}  →  ${task.destination}',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: cs.onSurfaceVariant),
            ),

            // ── Scene snapshot ────────────────────────────────────────────
            if (task.frameB64 != null && task.frameB64!.isNotEmpty) ...[
              const SizedBox(height: 10),
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: Image.memory(
                  base64Decode(task.frameB64!),
                  width: double.infinity,
                  height: 140,
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                ),
              ),
            ],

            // ── Detected objects ─────────────────────────────────────────
            if (task.detectedObjects.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                'Detected: ${task.detectedObjects.join(', ')}',
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: cs.onSurfaceVariant, fontSize: 11),
              ),
            ],

            const SizedBox(height: 12),

            // ── Phase stepper ─────────────────────────────────────────────
            ..._kPhases.map((phase) => _PhaseTile(
                  phase: phase,
                  currentPhase: task.phase,
                  taskStatus: task.status,
                )),

            // ── Confirm button (ask mode) ─────────────────────────────────
            if (task.isPendingConfirmation) ...[
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  icon: const Icon(Icons.play_arrow_rounded, size: 18),
                  label: const Text('Run ▶'),
                  onPressed: () => ref
                      .read(confirmTaskProvider.notifier)
                      .confirm(rrn: rrn, taskId: task.taskId),
                  style: FilledButton.styleFrom(
                    minimumSize: const Size(0, 40),
                  ),
                ),
              ),
            ],

            // ── Error ─────────────────────────────────────────────────────
            if (task.error != null) ...[
              const SizedBox(height: 6),
              Text(
                task.error!,
                style: TextStyle(fontSize: 11, color: cs.error),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

// ── Phase tile ────────────────────────────────────────────────────────────────

class _PhaseTile extends StatelessWidget {
  final String phase;
  final String currentPhase;
  final String taskStatus;

  const _PhaseTile({
    required this.phase,
    required this.currentPhase,
    required this.taskStatus,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    final phaseIndex = _kPhases.indexOf(phase);
    final currentIndex = _kPhases.indexOf(currentPhase);

    final isComplete = phaseIndex < currentIndex ||
        (phaseIndex == currentIndex &&
            (taskStatus == 'complete'));
    final isRunning = phaseIndex == currentIndex && taskStatus == 'running';
    final isFailed = phaseIndex == currentIndex &&
        (taskStatus == 'failed' || taskStatus == 'cancelled');

    Widget icon;
    if (isFailed) {
      icon = Icon(Icons.close_rounded, size: 16, color: cs.error);
    } else if (isComplete) {
      icon = Icon(Icons.check_rounded, size: 16, color: AppTheme.online);
    } else if (isRunning) {
      icon = SizedBox(
        width: 14,
        height: 14,
        child: CircularProgressIndicator(
          strokeWidth: 2,
          color: cs.primary,
        ),
      );
    } else {
      icon = Icon(Icons.radio_button_unchecked_rounded,
          size: 16, color: cs.onSurfaceVariant.withValues(alpha: 0.4));
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          SizedBox(width: 20, child: Center(child: icon)),
          const SizedBox(width: 10),
          Text(
            phase,
            style: TextStyle(
              fontSize: 13,
              color: isRunning
                  ? cs.primary
                  : isComplete
                      ? cs.onSurface
                      : cs.onSurfaceVariant.withValues(alpha: 0.5),
              fontWeight: isRunning ? FontWeight.w600 : FontWeight.normal,
            ),
          ),
        ],
      ),
    );
  }
}

// ── Status chip ───────────────────────────────────────────────────────────────

class _StatusChip extends StatelessWidget {
  final String status;
  const _StatusChip({required this.status});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final (label, color) = switch (status) {
      'pending_confirmation' => ('Awaiting', cs.secondary),
      'running' => ('Running', cs.primary),
      'complete' => ('Done', AppTheme.online),
      'failed' => ('Failed', cs.error),
      'cancelled' => ('Cancelled', cs.onSurfaceVariant),
      _ => (status, cs.onSurfaceVariant),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(label,
          style: TextStyle(
              fontSize: 11, color: color, fontWeight: FontWeight.w600)),
    );
  }
}
```

- [ ] **Step 4: Wire `TaskProgressCard` into the chat list in `robot_detail_screen.dart`**

Find where `ChatBubble` is built inside the list builder for commands. The pattern is inside a `ListView.builder` or similar. Look for the `commandsProvider` watch and find where `ChatBubble(` is called.

The replacement: wrap the `ChatBubble` call with a check for `taskId`:

```dart
// Find the existing ChatBubble build (response bubble for completed commands):
// Replace the entire result/response rendering block for completed commands

if (cmd.taskId != null)
  TaskProgressCard(rrn: widget.rrn, taskId: cmd.taskId!)
else
  ChatBubble(
    text: responseText,
    isUser: false,
    timestamp: cmd.completedAt ?? cmd.issuedAt,
  ),
```

Add import at top of `robot_detail_screen.dart`:
```dart
import '../widgets/task_progress_card.dart';
```

- [ ] **Step 5: Run widget tests**

```bash
cd /home/craigm26/opencastor-client
flutter test test/task_progress_card_test.dart -v
```

Expected: All tests PASS

- [ ] **Step 6: Verify full analyze**

```bash
cd /home/craigm26/opencastor-client
flutter analyze lib/ 2>&1 | tail -10
```

Expected: No errors

- [ ] **Step 7: Commit**

```bash
cd /home/craigm26/opencastor-client
git add lib/ui/widgets/task_progress_card.dart \
        lib/ui/robot_detail/robot_detail_screen.dart \
        test/task_progress_card_test.dart
git commit -m "feat(flutter): add TaskProgressCard widget and wire into chat"
```

---

## Task 9: Robot Settings Toggle (`task_execution`)

**Files:**
- Modify: `lib/ui/robot_capabilities/robot_capabilities_screen.dart` (add toggle section)

Context: The robot capabilities screen already has sections for hardware, software, contribute. Add a "Task Settings" section with the `task_execution` toggle. The toggle writes directly to `robots/{rrn}` Firestore field `task_execution`. The bridge reads this field from `self._rcan_config` on startup, and `_dispatch_pick_place` reads it at dispatch time from the same dict — but we also need the bridge to read from Firestore at dispatch time. We handle this by having `_dispatch_pick_place` read `task_execution` from the Firestore robot doc (fresh read).

**Note:** This task has two parts: Flutter toggle + bridge runtime read from Firestore.

- [ ] **Step 1: Add Firestore runtime read to `_dispatch_pick_place` in bridge.py**

In the `_dispatch_pick_place` method, replace the line:

```python
        task_execution = self._rcan_config.get("task_execution", "ask")
```

with:

```python
        # Read task_execution from Firestore at dispatch time (respects Flutter toggle)
        task_execution = self._rcan_config.get("task_execution", "ask")
        if self._db:
            try:
                robot_doc = self._robot_ref().get()
                if robot_doc.exists:
                    task_execution = robot_doc.to_dict().get("task_execution", task_execution)
            except Exception:
                pass  # fall back to config value
```

- [ ] **Step 2: Add toggle to `robot_capabilities_screen.dart`**

Find the end of the screen's main content `ListView` (look for where the last section ends before the closing `]` of the column children). Add a new section:

```dart
// ── Task Settings ─────────────────────────────────────────────────────────────
const SizedBox(height: 24),
_TaskSettingsSection(rrn: rrn),
```

Create the section widget inside the same file (at the bottom, before the last `}`):

```dart
class _TaskSettingsSection extends ConsumerStatefulWidget {
  final String rrn;
  const _TaskSettingsSection({required this.rrn});

  @override
  ConsumerState<_TaskSettingsSection> createState() =>
      _TaskSettingsSectionState();
}

class _TaskSettingsSectionState
    extends ConsumerState<_TaskSettingsSection> {
  bool _automatic = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _loadSetting();
  }

  Future<void> _loadSetting() async {
    final robot = await ref
        .read(robotRepositoryProvider)
        .getRobot(widget.rrn);
    if (robot != null && mounted) {
      setState(() {
        _automatic =
            (robot.telemetry['task_execution'] as String?) == 'automatic';
      });
    }
  }

  Future<void> _toggle(bool value) async {
    setState(() {
      _automatic = value;
      _saving = true;
    });
    try {
      await FirebaseFirestore.instance
          .collection('robots')
          .doc(widget.rrn)
          .update({'task_execution': value ? 'automatic' : 'ask'});
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to save: $e')),
        );
        setState(() => _automatic = !value); // revert
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Task Settings',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Card(
          child: SwitchListTile(
            title: const Text('Task execution'),
            subtitle: Text(
              _automatic
                  ? 'Automatic — arm executes immediately'
                  : 'Ask — confirm before executing',
              style: const TextStyle(fontSize: 12),
            ),
            value: _automatic,
            secondary: _saving
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.precision_manufacturing_outlined),
            onChanged: _saving ? null : _toggle,
          ),
        ),
      ],
    );
  }
}
```

Add import at top of file if not present:
```dart
import 'package:cloud_firestore/cloud_firestore.dart';
```

- [ ] **Step 3: Verify analyze passes**

```bash
cd /home/craigm26/opencastor-client
flutter analyze lib/ui/robot_capabilities/robot_capabilities_screen.dart 2>&1 | tail -5
```

Expected: No errors

- [ ] **Step 4: Run all Python tests including new bridge test for runtime read**

Add a test to `tests/test_pick_place_ux.py` verifying the Firestore runtime read:

```python
class TestDispatchPickPlaceFirestoreRead:
    def test_reads_task_execution_from_firestore(self):
        bridge = _make_bridge(task_execution="ask")  # config says ask

        # Firestore robot doc says automatic
        robot_doc = MagicMock()
        robot_doc.exists = True
        robot_doc.to_dict.return_value = {"task_execution": "automatic"}
        bridge._robot_ref().get.return_value = robot_doc

        with patch("httpx.Client") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"status": "complete", "log": []}
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.raise_for_status = MagicMock()
            mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

            # With automatic mode (from Firestore), should NOT call _wait_for_confirmation
            with patch.object(bridge, "_wait_for_confirmation") as mock_wait:
                bridge._dispatch_pick_place("lego", "bowl", {})
                mock_wait.assert_not_called()
```

```bash
cd /home/craigm26/OpenCastor
pytest tests/test_pick_place_ux.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit both repos**

```bash
cd /home/craigm26/OpenCastor
git add castor/cloud/bridge.py tests/test_pick_place_ux.py
git commit -m "feat(bridge): read task_execution from Firestore at dispatch time"

cd /home/craigm26/opencastor-client
git add lib/ui/robot_capabilities/robot_capabilities_screen.dart
git commit -m "feat(flutter): add task_execution ask/automatic toggle in settings"
```

---

## Self-Review

**1. Spec coverage:**
- ✓ Natural language intent detection → `_detect_pick_place_intent`
- ✓ Firestore task doc schema → `_write_task_doc` in bridge + `TaskDoc` model
- ✓ Gateway phase writes → `_write_task_phase` in api.py
- ✓ Flutter `TaskProgressCard` with all 4 phases
- ✓ Scene snapshot rendering from `frame_b64`
- ✓ `[Run ▶]` button in ask mode
- ✓ `task_execution: ask | automatic` toggle in settings
- ✓ Bridge reads toggle at dispatch time (Firestore)
- ✓ Error handling: cancelled/failed states render correctly in card
- ⚠ `detected_objects` written by bridge's `_dispatch_pick_place` not by gateway — spec says gateway writes at SCAN. Added `frame_b64` + `detected_objects` write path via `_write_task_phase` with extra_fields. But bridge doesn't call detection before calling gateway. **Gap**: bridge should call `/api/detection/latest` before dispatching, write results to task doc. Adding to Task 4 Step 3.

**Gap fix — add to Task 4 Step 3 `_dispatch_pick_place`:**
After `self._write_task_doc(...)`, add detection pre-scan:

```python
        # Pre-scan: fetch latest detection to populate detected_objects + frame
        try:
            import httpx as _httpx
            with _httpx.Client(timeout=5.0) as _client:
                _det_resp = _client.get(
                    f"{self.gateway_url}/api/detection/latest",
                    headers=self._auth_headers(),
                )
                if _det_resp.status_code == 200:
                    _det = _det_resp.json()
                    _objects = [
                        d.get("label", "") for d in _det.get("detections", [])
                    ]
                    self._update_task_doc(task_id, {
                        "detected_objects": _objects,
                        "phase": "SCAN",
                        "status": initial_status,
                    })
        except Exception:
            pass  # best-effort
```

**2. Placeholder scan:** No TBDs. All code is complete. ✓

**3. Type consistency:** `TaskDoc` fields match throughout: `frameB64` in Dart (camelCase), `frame_b64` in Firestore/Python. `taskId` in Dart, `task_id` in Firestore. All consistent. ✓
