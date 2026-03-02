"""Tests for BehaviorRunner._step_retry — issue #365."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _make_runner():
    from castor.behaviors import BehaviorRunner

    runner = BehaviorRunner(driver=MagicMock(), brain=None, speaker=None)
    runner._running = True
    return runner


# ── Dispatch table ─────────────────────────────────────────────────────────────


def test_retry_step_registered():
    runner = _make_runner()
    assert "retry" in runner._step_handlers


# ── Empty steps ────────────────────────────────────────────────────────────────


def test_retry_empty_steps_skips(caplog):
    import logging

    runner = _make_runner()
    with caplog.at_level(logging.WARNING, logger="OpenCastor.Behaviors"):
        runner._step_retry({"max_attempts": 3, "steps": []})
    assert any("empty" in r.message.lower() or "skipping" in r.message.lower() for r in caplog.records)


# ── Success on first attempt ───────────────────────────────────────────────────


def test_retry_succeeds_on_first_attempt():
    runner = _make_runner()
    calls = []

    def _fake_run(steps, label):
        calls.append(1)
        # running stays True → success

    runner._run_step_list = _fake_run
    runner._step_retry({"max_attempts": 3, "backoff_s": 0, "steps": [{"type": "wait"}]})
    assert len(calls) == 1


# ── Retry on failure ───────────────────────────────────────────────────────────


def test_retry_attempts_up_to_max():
    runner = _make_runner()
    calls = []
    attempt_count = [0]

    def _fake_run(steps, label):
        calls.append(1)
        attempt_count[0] += 1
        # Simulate failure by setting _running = False (then retry re-arms it)
        runner._running = False

    runner._run_step_list = _fake_run
    runner._stop_event.wait = lambda timeout=None: None  # instant
    runner._step_retry({"max_attempts": 3, "backoff_s": 0, "steps": [{"type": "wait"}]})
    assert len(calls) == 3


def test_retry_succeeds_on_second_attempt():
    runner = _make_runner()
    calls = []

    def _fake_run(steps, label):
        calls.append(1)
        if len(calls) == 1:
            runner._running = False  # first attempt fails

    runner._run_step_list = _fake_run
    runner._stop_event.wait = lambda timeout=None: None
    runner._step_retry({"max_attempts": 3, "backoff_s": 0, "steps": [{"type": "wait"}]})
    assert len(calls) == 2


# ── max_attempts ──────────────────────────────────────────────────────────────


def test_retry_default_max_attempts_is_3():
    runner = _make_runner()
    calls = []

    def _fake_run(steps, label):
        calls.append(1)
        runner._running = False

    runner._run_step_list = _fake_run
    runner._stop_event.wait = lambda timeout=None: None
    runner._step_retry({"backoff_s": 0, "steps": [{"type": "wait"}]})
    assert len(calls) == 3


def test_retry_max_attempts_one_no_retry():
    runner = _make_runner()
    calls = []

    def _fake_run(steps, label):
        calls.append(1)
        runner._running = False

    runner._run_step_list = _fake_run
    runner._step_retry({"max_attempts": 1, "backoff_s": 0, "steps": [{"type": "wait"}]})
    assert len(calls) == 1


# ── backoff_s ─────────────────────────────────────────────────────────────────


def test_retry_uses_stop_event_for_backoff():
    runner = _make_runner()
    waits = []

    def _fake_wait(timeout=None):
        waits.append(timeout)

    runner._stop_event.wait = _fake_wait
    calls = []

    def _fake_run(steps, label):
        calls.append(1)
        if len(calls) < 2:
            runner._running = False

    runner._run_step_list = _fake_run
    runner._step_retry({"max_attempts": 3, "backoff_s": 2.5, "steps": [{"type": "wait"}]})
    assert any(w == 2.5 for w in waits)


# ── Stop propagation ──────────────────────────────────────────────────────────


def test_retry_stops_when_not_running_before_start():
    runner = _make_runner()
    runner._running = False
    calls = []
    runner._run_step_list = lambda steps, label: calls.append(1)
    runner._step_retry({"max_attempts": 3, "steps": [{"type": "wait"}]})
    assert len(calls) == 0
