"""Tests for BehaviorRunner break_on step (Issue #402)."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from castor.behaviors import BehaviorRunner, _BreakLoop


@pytest.fixture
def runner():
    r = BehaviorRunner(config={}, driver=MagicMock(), brain=MagicMock())
    r._running = True
    return r


# ── Sentinel class ────────────────────────────────────────────────────────────


def test_break_loop_is_importable():
    assert _BreakLoop is not None
    assert issubclass(_BreakLoop, Exception)


def test_break_loop_is_exception():
    bl = _BreakLoop("test")
    assert isinstance(bl, Exception)


# ── Dispatch table ────────────────────────────────────────────────────────────


def test_break_on_registered_in_dispatch(runner):
    assert "break_on" in runner._step_handlers


def test_break_on_handler_is_callable(runner):
    assert callable(runner._step_handlers["break_on"])


def test_runner_has_step_break_on_method(runner):
    assert hasattr(runner, "_step_break_on")
    assert callable(runner._step_break_on)


# ── Condition is True → raises _BreakLoop ─────────────────────────────────────


def test_break_on_true_condition_raises_break_loop(runner):
    with patch.object(runner, "_eval_condition", return_value=True):
        with pytest.raises(_BreakLoop):
            runner._step_break_on({"condition": "1 > 0"})


def test_break_on_true_condition_raised_via_run_step(runner):
    """_BreakLoop raised via the dispatch table path."""
    with patch.object(runner, "_eval_condition", return_value=True):
        with pytest.raises(_BreakLoop):
            runner._step_handlers["break_on"]({"condition": "1 > 0"})


# ── Condition is False → does NOT raise ───────────────────────────────────────


def test_break_on_false_condition_does_not_raise(runner):
    with patch.object(runner, "_eval_condition", return_value=False):
        # Should complete without raising
        runner._step_break_on({"condition": "0 > 1"})


def test_break_on_false_condition_returns_none(runner):
    with patch.object(runner, "_eval_condition", return_value=False):
        result = runner._step_break_on({"condition": "0 > 1"})
    assert result is None


# ── No condition → unconditional break ────────────────────────────────────────


def test_break_on_no_condition_always_breaks(runner):
    with pytest.raises(_BreakLoop):
        runner._step_break_on({})


def test_break_on_empty_condition_always_breaks(runner):
    with pytest.raises(_BreakLoop):
        runner._step_break_on({"condition": ""})


# ── Eval error → does NOT break ───────────────────────────────────────────────


def test_break_on_eval_error_does_not_raise_break_loop(runner, caplog):
    with patch.object(runner, "_eval_condition", side_effect=ValueError("bad")), \
         caplog.at_level(logging.WARNING, logger="OpenCastor.Behaviors"):
        # Must not raise _BreakLoop or any other exception
        runner._step_break_on({"condition": "bad_expr"})
    assert any("eval" in r.message.lower() or "error" in r.message.lower() for r in caplog.records)


# ── while_true integration ────────────────────────────────────────────────────


def test_while_true_exits_on_break_on(runner):
    """while_true loop exits cleanly when break_on raises _BreakLoop."""
    behavior = {
        "name": "test_break",
        "steps": [{
            "type": "while_true",
            "max_iterations": 100,
            "inner_steps": [
                {"type": "break_on", "condition": "1 > 0"}
            ]
        }]
    }
    with patch.object(runner, "_eval_condition", return_value=True):
        runner.run(behavior)
    # If we get here without hanging, the break worked


def test_while_true_break_on_exits_after_first_iteration(runner):
    """Verify the loop body runs exactly once before break_on fires."""
    count = [0]

    def fake_noop(step):
        count[0] += 1

    runner._step_handlers["noop"] = fake_noop

    step = {
        "type": "while_true",
        "max_iterations": 50,
        "inner_steps": [
            {"type": "noop"},
            {"type": "break_on", "condition": "1 > 0"},
        ]
    }
    with patch.object(runner, "_eval_condition", return_value=True):
        runner._step_while_true(step)

    assert count[0] == 1


# ── for_each integration ──────────────────────────────────────────────────────


def test_for_each_exits_on_break_on(runner):
    """for_each loop exits early when break_on raises _BreakLoop."""
    count = [0]

    def fake_noop(step):
        count[0] += 1

    runner._step_handlers["noop"] = fake_noop

    step = {
        "type": "for_each",
        "items": [1, 2, 3, 4, 5],
        "inner_steps": [
            {"type": "noop"},
            {"type": "break_on", "condition": "1 > 0"},
        ]
    }
    with patch.object(runner, "_eval_condition", return_value=True):
        runner._step_for_each(step)

    # noop runs once (first iteration), then break_on fires
    assert count[0] == 1


# ── repeat_until integration ──────────────────────────────────────────────────


def test_repeat_until_exits_on_break_on(runner):
    """repeat_until loop exits early when break_on is triggered."""
    count = [0]

    def fake_noop(step):
        count[0] += 1

    runner._step_handlers["noop"] = fake_noop

    step = {
        "type": "repeat_until",
        "sensor": "none",
        "field": None,
        "op": "eq",
        "value": 999,
        "max_count": 50,
        "inner_steps": [
            {"type": "noop"},
            {"type": "break_on", "condition": "1 > 0"},
        ]
    }

    # _eval_condition: the repeat_until exit condition (4 args) vs break_on (1 arg)
    # We need break_on's _eval_condition(str) to return True.
    # repeat_until calls the static _eval_condition(sensor, field, op, value) which
    # is a different signature — patch the instance method to handle both.
    original_static = BehaviorRunner._eval_condition.__func__ if hasattr(
        BehaviorRunner._eval_condition, "__func__"
    ) else None

    def smart_eval(self_or_condition, *args):
        # When called as instance method with a string condition
        if isinstance(self_or_condition, str) or (
            not isinstance(self_or_condition, BehaviorRunner) and isinstance(self_or_condition, str)
        ):
            return True
        # Instance method call: self_or_condition is str (condition arg on self=runner)
        return True

    with patch.object(runner, "_eval_condition", return_value=True):
        # repeat_until's _eval_condition has 4 args — we need to handle that separately
        # Simplest: replace both paths via patching the static too
        with patch.object(BehaviorRunner, "_eval_condition", staticmethod(lambda *a: False)):
            # Now instance _eval_condition returns False (exit condition never met)
            # but break_on uses self._eval_condition(condition_str) which is also patched
            # This is tricky — use a side effect approach instead
            pass

    # Simpler approach: just verify the loop doesn't run 50 times
    call_count = [0]

    def counting_eval(condition):
        call_count[0] += 1
        return True  # break_on will always fire

    with patch.object(runner, "_eval_condition", side_effect=counting_eval):
        # patch static _eval_condition (used by repeat_until exit check) to return False
        with patch.object(
            type(runner),
            "_eval_condition",
            new=lambda self, cond: True,
        ):
            runner._step_repeat_until(step)

    # If break_on worked, noop ran only once
    assert count[0] == 1
