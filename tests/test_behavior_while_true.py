"""Tests for BehaviorRunner while_true step (#386)."""

import time
from unittest.mock import MagicMock

from castor.behaviors import BehaviorRunner


def _make_runner():
    driver = MagicMock()
    runner = BehaviorRunner(driver=driver, config={})
    runner._running = True
    return runner


# ── dispatch table ────────────────────────────────────────────────────────────

def test_while_true_in_dispatch_table():
    runner = _make_runner()
    assert "while_true" in runner._step_handlers


def test_while_true_handler_callable():
    runner = _make_runner()
    assert callable(runner._step_handlers["while_true"])


# ── missing / empty inner_steps ───────────────────────────────────────────────

def test_while_true_no_inner_steps_skips(caplog):
    import logging

    runner = _make_runner()
    with caplog.at_level(logging.WARNING):
        runner._step_while_true({})
    assert any("inner_steps" in r.message for r in caplog.records)


def test_while_true_empty_inner_steps_skips(caplog):
    import logging

    runner = _make_runner()
    with caplog.at_level(logging.WARNING):
        runner._step_while_true({"inner_steps": []})
    assert any("inner_steps" in r.message for r in caplog.records)


# ── max_iterations guard ──────────────────────────────────────────────────────

def test_while_true_max_iterations_stops():
    runner = _make_runner()
    count = [0]

    def fake_wait(step):
        count[0] += 1

    runner._step_handlers["wait"] = fake_wait
    runner._step_while_true(
        {"inner_steps": [{"type": "wait", "seconds": 0}], "max_iterations": 5}
    )
    assert count[0] == 5


def test_while_true_max_iterations_one():
    runner = _make_runner()
    count = [0]

    def fake_wait(step):
        count[0] += 1

    runner._step_handlers["wait"] = fake_wait
    runner._step_while_true(
        {"inner_steps": [{"type": "wait", "seconds": 0}], "max_iterations": 1}
    )
    assert count[0] == 1


# ── timeout guard ─────────────────────────────────────────────────────────────

def test_while_true_timeout_stops():
    runner = _make_runner()
    start = time.monotonic()
    runner._step_while_true(
        {
            "inner_steps": [{"type": "wait", "seconds": 0}],
            "timeout_s": 0.05,
            "max_iterations": 999,
        }
    )
    elapsed = time.monotonic() - start
    assert elapsed < 2.0  # should stop well within 2 seconds


# ── _running flag stops loop ──────────────────────────────────────────────────

def test_while_true_stops_when_running_false():
    runner = _make_runner()
    count = [0]

    def fake_wait(step):
        count[0] += 1
        runner._running = False  # stop after first iteration

    runner._step_handlers["wait"] = fake_wait
    runner._step_while_true(
        {"inner_steps": [{"type": "wait", "seconds": 0}], "max_iterations": 100}
    )
    assert count[0] == 1


# ── returns None ──────────────────────────────────────────────────────────────

def test_while_true_returns_none():
    runner = _make_runner()
    result = runner._step_while_true(
        {"inner_steps": [{"type": "wait", "seconds": 0}], "max_iterations": 1}
    )
    assert result is None


# ── dwell_s parameter ────────────────────────────────────────────────────────

def test_while_true_dwell_s_does_not_raise():
    runner = _make_runner()
    runner._step_while_true(
        {
            "inner_steps": [{"type": "wait", "seconds": 0}],
            "max_iterations": 2,
            "dwell_s": 0.0,
        }
    )


# ── multiple inner steps executed each iteration ─────────────────────────────

def test_while_true_runs_all_inner_steps():
    runner = _make_runner()
    executed = []

    def fake_a(step):
        executed.append("a")

    def fake_b(step):
        executed.append("b")

    runner._step_handlers["type_a"] = fake_a
    runner._step_handlers["type_b"] = fake_b
    runner._step_while_true(
        {
            "inner_steps": [{"type": "type_a"}, {"type": "type_b"}],
            "max_iterations": 2,
        }
    )
    assert executed == ["a", "b", "a", "b"]
