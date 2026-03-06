"""Tests for BehaviorRunner._step_countdown (Issue #423)."""

from unittest.mock import MagicMock, call, patch

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


def test_countdown_registered_in_dispatch(runner):
    assert "countdown" in runner._step_handlers


def test_countdown_handler_is_callable(runner):
    assert callable(runner._step_handlers["countdown"])


def test_countdown_method_exists(runner):
    assert hasattr(runner, "_step_countdown")
    assert callable(runner._step_countdown)


# ------------------------------------------------------------------
# Basic operation
# ------------------------------------------------------------------


def test_countdown_does_not_raise(runner):
    with patch("castor.behaviors.time.sleep"):
        runner._step_countdown({"from_s": 3, "interval_s": 0.0, "speak": False})


def test_countdown_from_zero_completes_immediately(runner):
    """from_s=0 means just emit 0, no sleeps needed."""
    with patch("castor.behaviors.time.sleep") as mock_sleep:
        runner._step_countdown({"from_s": 0, "interval_s": 1.0, "speak": False})
    mock_sleep.assert_not_called()


def test_countdown_correct_number_of_sleeps(runner):
    """from_s=3 should sleep 3 times (between 3→2, 2→1, 1→0)."""
    with patch("castor.behaviors.time.sleep") as mock_sleep:
        runner._step_countdown({"from_s": 3, "interval_s": 0.5, "speak": False})
    assert mock_sleep.call_count == 3


def test_countdown_uses_interval_s_as_sleep_duration(runner):
    """Each sleep should use the interval_s value."""
    with patch("castor.behaviors.time.sleep") as mock_sleep:
        runner._step_countdown({"from_s": 2, "interval_s": 0.75, "speak": False})
    for c in mock_sleep.call_args_list:
        assert c == call(0.75)


def test_countdown_custom_from_s(runner):
    """from_s=5 should produce 6 values (5, 4, 3, 2, 1, 0) and 5 sleeps."""
    with patch("castor.behaviors.time.sleep") as mock_sleep:
        runner._step_countdown({"from_s": 5, "interval_s": 0.0})
    assert mock_sleep.call_count == 5


def test_countdown_default_from_s_is_10(runner):
    """Default from_s should be 10 → 10 sleeps."""
    with patch("castor.behaviors.time.sleep") as mock_sleep:
        runner._step_countdown({"interval_s": 0.0})
    assert mock_sleep.call_count == 10


def test_countdown_default_interval_s_is_one(runner):
    """Default interval_s should be 1.0."""
    with patch("castor.behaviors.time.sleep") as mock_sleep:
        runner._step_countdown({"from_s": 1})
    # One sleep of 1.0s between 1 and 0
    assert mock_sleep.call_count == 1
    mock_sleep.assert_called_with(1.0)


# ------------------------------------------------------------------
# speak behaviour
# ------------------------------------------------------------------


def test_countdown_speak_false_does_not_call_speak(runner):
    """speak=False should not call the speaker."""
    speaker = MagicMock()
    runner.speaker = speaker
    with patch("castor.behaviors.time.sleep"):
        runner._step_countdown({"from_s": 3, "interval_s": 0.0, "speak": False})
    speaker.say.assert_not_called()


def test_countdown_speak_true_calls_speaker_for_each_number(runner):
    """speak=True should call speaker.say() for each number from from_s down to 0."""
    speaker = MagicMock()
    runner.speaker = speaker
    with patch("castor.behaviors.time.sleep"):
        runner._step_countdown({"from_s": 3, "interval_s": 0.0, "speak": True})
    assert speaker.say.call_count == 4  # 3, 2, 1, 0
    calls = [c.args[0] for c in speaker.say.call_args_list]
    assert calls == ["3", "2", "1", "0"]


def test_countdown_speak_true_no_speaker_does_not_raise(runner):
    """speak=True with no speaker should not raise (logs warning instead)."""
    runner.speaker = None
    with patch("castor.behaviors.time.sleep"):
        runner._step_countdown({"from_s": 2, "interval_s": 0.0, "speak": True})


# ------------------------------------------------------------------
# Early stop when _running becomes False
# ------------------------------------------------------------------


def test_countdown_stops_early_when_running_false(runner):
    """When _running is set to False mid-countdown, iteration stops early."""
    counts_seen = []

    def fake_sleep(s):
        # After the first sleep, stop the runner
        counts_seen.append("sleep")
        runner._running = False

    runner._running = True
    with patch("castor.behaviors.time.sleep", side_effect=fake_sleep):
        runner._step_countdown({"from_s": 10, "interval_s": 0.001, "speak": False})

    # Should have stopped after just one sleep, not all 10
    assert len(counts_seen) < 10


def test_countdown_via_dispatch_table(runner):
    """Dispatching via _step_handlers['countdown'] should work correctly."""
    with patch("castor.behaviors.time.sleep") as mock_sleep:
        runner._step_handlers["countdown"]({"from_s": 2, "interval_s": 0.0, "speak": False})
    assert mock_sleep.call_count == 2
