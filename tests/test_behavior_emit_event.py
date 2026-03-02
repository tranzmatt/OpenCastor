"""Tests for BehaviorRunner._step_emit_event (Issue #429)."""

import threading
import time
from unittest.mock import MagicMock

import pytest

from castor.behaviors import BehaviorRunner


@pytest.fixture
def runner():
    r = BehaviorRunner(config={}, driver=MagicMock(), brain=MagicMock())
    r._running = True
    return r


# ------------------------------------------------------------------
# Registration / structural checks
# ------------------------------------------------------------------


def test_emit_event_registered_in_dispatch(runner):
    assert "emit_event" in runner._step_handlers


def test_emit_event_handler_is_callable(runner):
    assert callable(runner._step_handlers["emit_event"])


def test_emit_event_method_exists(runner):
    assert hasattr(runner, "_step_emit_event")
    assert callable(runner._step_emit_event)


# ------------------------------------------------------------------
# Basic operation
# ------------------------------------------------------------------


def test_emit_event_does_not_raise(runner):
    runner._step_emit_event({"event": "test_event"})


def test_emit_event_creates_event_if_not_present(runner):
    assert "new_ev" not in runner._events
    runner._step_emit_event({"event": "new_ev"})
    with runner._events_lock:
        assert "new_ev" in runner._events


def test_emit_event_sets_event_after_create(runner):
    runner._step_emit_event({"event": "brand_new"})
    with runner._events_lock:
        assert runner._events["brand_new"].is_set()


def test_emit_event_sets_existing_event(runner):
    existing = threading.Event()
    runner._events["existing_ev"] = existing
    runner._step_emit_event({"event": "existing_ev"})
    assert existing.is_set()


def test_emit_event_sets_cleared_event(runner):
    """emit_event should re-set an event that was previously cleared."""
    ev = threading.Event()
    ev.set()
    ev.clear()
    assert not ev.is_set()
    runner._events["cleared_ev"] = ev
    runner._step_emit_event({"event": "cleared_ev"})
    assert ev.is_set()


def test_emit_event_preserves_existing_event_object(runner):
    """emit_event should use the existing threading.Event, not replace it."""
    existing = threading.Event()
    runner._events["preserve_ev"] = existing
    runner._step_emit_event({"event": "preserve_ev"})
    with runner._events_lock:
        assert runner._events["preserve_ev"] is existing


# ------------------------------------------------------------------
# Missing event key
# ------------------------------------------------------------------


def test_emit_event_missing_event_key_skips(runner):
    """Missing 'event' key should not raise and should not create any event."""
    before = set(runner._events.keys())
    runner._step_emit_event({})
    after = set(runner._events.keys())
    assert before == after


def test_emit_event_empty_event_key_skips(runner):
    """Empty string 'event' key should not raise."""
    runner._step_emit_event({"event": ""})


# ------------------------------------------------------------------
# Interaction with wait_for_event
# ------------------------------------------------------------------


def test_emit_event_unblocks_wait_for_event(runner):
    """emit_event should unblock a concurrent wait_for_event step."""
    results = []

    def waiter():
        runner._step_wait_for_event({"event": "shared_ev", "timeout_s": 2.0, "clear_after": False})
        results.append("unblocked")

    t = threading.Thread(target=waiter, daemon=True)
    t.start()
    time.sleep(0.05)  # let waiter block first
    runner._step_emit_event({"event": "shared_ev"})
    t.join(timeout=1.0)
    assert "unblocked" in results


# ------------------------------------------------------------------
# Via dispatch table
# ------------------------------------------------------------------


def test_emit_event_via_dispatch_table(runner):
    handler = runner._step_handlers["emit_event"]
    handler({"event": "dispatch_ev"})
    with runner._events_lock:
        assert "dispatch_ev" in runner._events
        assert runner._events["dispatch_ev"].is_set()
