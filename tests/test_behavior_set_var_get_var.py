"""Tests for BehaviorRunner set_var / get_var steps — issue #368."""

from __future__ import annotations

from unittest.mock import MagicMock


def _make_runner():
    from castor.behaviors import BehaviorRunner

    runner = BehaviorRunner(driver=MagicMock(), brain=None, speaker=None)
    runner._running = True
    return runner


# ── Dispatch table ─────────────────────────────────────────────────────────────


def test_set_var_registered():
    runner = _make_runner()
    assert "set_var" in runner._step_handlers


def test_get_var_registered():
    runner = _make_runner()
    assert "get_var" in runner._step_handlers


# ── set_var ────────────────────────────────────────────────────────────────────


def test_set_var_stores_value():
    runner = _make_runner()
    runner._step_set_var({"name": "speed", "value": 1.5})
    assert runner._vars["speed"] == 1.5


def test_set_var_stores_string():
    runner = _make_runner()
    runner._step_set_var({"name": "mode", "value": "patrol"})
    assert runner._vars["mode"] == "patrol"


def test_set_var_stores_none_value():
    runner = _make_runner()
    runner._step_set_var({"name": "empty", "value": None})
    assert "empty" in runner._vars
    assert runner._vars["empty"] is None


def test_set_var_missing_name_skips(caplog):
    import logging

    runner = _make_runner()
    with caplog.at_level(logging.WARNING, logger="OpenCastor.Behaviors"):
        runner._step_set_var({"value": 99})
    assert any("name" in r.message.lower() for r in caplog.records)


def test_set_var_overwrites_existing():
    runner = _make_runner()
    runner._vars["x"] = 1
    runner._step_set_var({"name": "x", "value": 42})
    assert runner._vars["x"] == 42


# ── get_var ────────────────────────────────────────────────────────────────────


def test_get_var_missing_name_skips(caplog):
    import logging

    runner = _make_runner()
    with caplog.at_level(logging.WARNING, logger="OpenCastor.Behaviors"):
        runner._step_get_var({"steps": []})
    assert any("name" in r.message.lower() for r in caplog.records)


def test_get_var_substitutes_placeholder():
    runner = _make_runner()
    runner._vars["dist"] = 2.0
    executed = []

    def _fake_run(steps, label):
        executed.extend(steps)

    runner._run_step_list = _fake_run
    runner._step_get_var(
        {
            "name": "dist",
            "steps": [{"type": "waypoint", "distance_m": "$var.dist"}],
        }
    )
    assert len(executed) == 1
    assert executed[0]["distance_m"] == 2.0


def test_get_var_uses_default_when_unset():
    runner = _make_runner()
    executed = []

    def _fake_run(steps, label):
        executed.extend(steps)

    runner._run_step_list = _fake_run
    runner._step_get_var(
        {
            "name": "missing",
            "default": 99,
            "steps": [{"type": "wait", "seconds": "$var.missing"}],
        }
    )
    assert executed[0]["seconds"] == 99


def test_get_var_default_none_when_not_provided():
    runner = _make_runner()
    executed = []

    def _fake_run(steps, label):
        executed.extend(steps)

    runner._run_step_list = _fake_run
    runner._step_get_var(
        {
            "name": "unset",
            "steps": [{"type": "wait", "seconds": "$var.unset"}],
        }
    )
    assert executed[0]["seconds"] is None


def test_get_var_non_placeholder_key_unchanged():
    runner = _make_runner()
    runner._vars["n"] = 5
    executed = []

    def _fake_run(steps, label):
        executed.extend(steps)

    runner._run_step_list = _fake_run
    runner._step_get_var(
        {
            "name": "n",
            "steps": [{"type": "wait", "seconds": 3, "label": "constant"}],
        }
    )
    assert executed[0]["seconds"] == 3
    assert executed[0]["label"] == "constant"


# ── _vars cleared on stop ──────────────────────────────────────────────────────


def test_vars_cleared_on_stop():
    runner = _make_runner()
    runner._vars["key"] = "value"
    runner.stop()
    assert runner._vars == {}


# ── round-trip: set_var then get_var ──────────────────────────────────────────


def test_set_then_get_var_round_trip():
    runner = _make_runner()
    runner._step_set_var({"name": "count", "value": 7})

    executed = []

    def _fake_run(steps, label):
        executed.extend(steps)

    runner._run_step_list = _fake_run
    runner._step_get_var(
        {
            "name": "count",
            "steps": [{"type": "repeat", "times": "$var.count"}],
        }
    )
    assert executed[0]["times"] == 7
