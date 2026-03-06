"""Tests for BehaviorRunner unless step (Issue #400)."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from castor.behaviors import BehaviorRunner


@pytest.fixture
def runner():
    r = BehaviorRunner(config={}, driver=MagicMock(), brain=MagicMock())
    r._running = True
    return r


# ── Dispatch table ─────────────────────────────────────────────────────────────


def test_unless_registered_in_dispatch(runner):
    assert "unless" in runner._step_handlers


def test_unless_handler_is_callable(runner):
    assert callable(runner._step_handlers["unless"])


def test_runner_has_step_unless_method(runner):
    assert hasattr(runner, "_step_unless")
    assert callable(runner._step_unless)


# ── Condition is True → skips inner_steps ─────────────────────────────────────


def test_unless_true_condition_skips_inner_steps(runner):
    """When condition is True, inner_steps must NOT run."""
    ran = []

    def fake_wait(step):
        ran.append("wait")

    runner._step_handlers["wait"] = fake_wait

    with patch.object(runner, "_eval_condition", return_value=True):
        runner._step_unless(
            {
                "condition": "1 > 0",
                "inner_steps": [{"type": "wait", "duration_s": 1}],
            }
        )

    assert ran == [], "inner_steps should be skipped when condition is True"


def test_unless_true_condition_does_not_call_run_step_list(runner):
    with (
        patch.object(runner, "_eval_condition", return_value=True),
        patch.object(runner, "_run_step_list") as mock_rsl,
    ):
        runner._step_unless(
            {
                "condition": "1 > 0",
                "inner_steps": [{"type": "wait", "duration_s": 1}],
            }
        )
    mock_rsl.assert_not_called()


# ── Condition is False → runs inner_steps ─────────────────────────────────────


def test_unless_false_condition_runs_inner_steps(runner):
    """When condition is False, inner_steps MUST run."""
    with (
        patch.object(runner, "_eval_condition", return_value=False),
        patch.object(runner, "_run_step_list") as mock_rsl,
    ):
        runner._step_unless(
            {
                "condition": "0 > 1",
                "inner_steps": [{"type": "wait", "duration_s": 1}],
            }
        )
    mock_rsl.assert_called_once()


def test_unless_false_condition_passes_inner_steps_to_run_step_list(runner):
    inner = [{"type": "wait", "duration_s": 1}]
    with (
        patch.object(runner, "_eval_condition", return_value=False),
        patch.object(runner, "_run_step_list") as mock_rsl,
    ):
        runner._step_unless({"condition": "0 > 1", "inner_steps": inner})
    args = mock_rsl.call_args[0]
    assert args[0] == inner


# ── Missing / empty condition ─────────────────────────────────────────────────


def test_unless_missing_condition_skips_and_warns(runner, caplog):
    with (
        patch.object(runner, "_run_step_list") as mock_rsl,
        caplog.at_level(logging.WARNING, logger="OpenCastor.Behaviors"),
    ):
        runner._step_unless({"inner_steps": [{"type": "wait"}]})
    mock_rsl.assert_not_called()
    assert any("condition" in r.message.lower() for r in caplog.records)


def test_unless_empty_condition_string_skips(runner, caplog):
    with (
        patch.object(runner, "_run_step_list") as mock_rsl,
        caplog.at_level(logging.WARNING, logger="OpenCastor.Behaviors"),
    ):
        runner._step_unless({"condition": "", "inner_steps": [{"type": "wait"}]})
    mock_rsl.assert_not_called()


# ── Missing / empty inner_steps ───────────────────────────────────────────────


def test_unless_empty_inner_steps_skips_and_warns(runner, caplog):
    with (
        patch.object(runner, "_eval_condition", return_value=False),
        patch.object(runner, "_run_step_list") as mock_rsl,
        caplog.at_level(logging.WARNING, logger="OpenCastor.Behaviors"),
    ):
        runner._step_unless({"condition": "0 > 1", "inner_steps": []})
    mock_rsl.assert_not_called()
    assert any("inner_steps" in r.message.lower() for r in caplog.records)


def test_unless_none_inner_steps_skips(runner):
    with (
        patch.object(runner, "_eval_condition", return_value=False),
        patch.object(runner, "_run_step_list") as mock_rsl,
    ):
        runner._step_unless({"condition": "0 > 1", "inner_steps": None})
    mock_rsl.assert_not_called()


# ── Eval error ────────────────────────────────────────────────────────────────


def test_unless_eval_error_does_not_raise(runner, caplog):
    """A bad condition expression must not propagate an exception."""
    with (
        patch.object(runner, "_eval_condition", side_effect=ValueError("bad expr")),
        patch.object(runner, "_run_step_list") as mock_rsl,
        caplog.at_level(logging.WARNING, logger="OpenCastor.Behaviors"),
    ):
        runner._step_unless(
            {
                "condition": "not_a_number > 5",
                "inner_steps": [{"type": "wait"}],
            }
        )
    # Should not raise, should not run inner_steps
    mock_rsl.assert_not_called()
    assert any("eval" in r.message.lower() or "error" in r.message.lower() for r in caplog.records)


# ── Integration: real _eval_condition ─────────────────────────────────────────


def test_unless_real_condition_true_skips(runner):
    ran = []

    def fake_wait(step):
        ran.append("ran")

    runner._step_handlers["wait"] = fake_wait
    # "5 > 3" is True → should skip inner_steps
    runner._step_unless(
        {
            "condition": "5 > 3",
            "inner_steps": [{"type": "wait"}],
        }
    )
    assert ran == []


def test_unless_real_condition_false_runs(runner):
    ran = []

    def fake_wait(step):
        ran.append("ran")

    runner._step_handlers["wait"] = fake_wait
    # "0 > 3" is False → should run inner_steps
    runner._step_unless(
        {
            "condition": "0 > 3",
            "inner_steps": [{"type": "wait"}],
        }
    )
    assert ran == ["ran"]
