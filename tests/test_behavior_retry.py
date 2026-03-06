"""Tests for BehaviorRunner retry step (#396)."""

from unittest.mock import MagicMock

from castor.behaviors import BehaviorRunner


def _make_runner():
    driver = MagicMock()
    runner = BehaviorRunner(driver=driver, config={})
    runner._running = True
    return runner


# ── dispatch table ────────────────────────────────────────────────────────────


def test_retry_in_dispatch_table():
    runner = _make_runner()
    assert "retry" in runner._step_handlers


def test_retry_handler_callable():
    runner = _make_runner()
    assert callable(runner._step_handlers["retry"])


# ── empty steps ───────────────────────────────────────────────────────────────


def test_retry_empty_steps_skips(caplog):
    import logging

    runner = _make_runner()
    with caplog.at_level(logging.WARNING):
        runner._step_retry({"steps": []})
    assert any("steps" in r.message.lower() for r in caplog.records)


def test_retry_no_steps_key_skips(caplog):
    import logging

    runner = _make_runner()
    with caplog.at_level(logging.WARNING):
        runner._step_retry({})
    assert any("steps" in r.message.lower() for r in caplog.records)


# ── success on first attempt ──────────────────────────────────────────────────


def test_retry_succeeds_on_first_attempt():
    runner = _make_runner()
    count = [0]

    def fake_wait(step):
        count[0] += 1

    runner._step_handlers["wait"] = fake_wait
    runner._step_retry(
        {"steps": [{"type": "wait", "seconds": 0}], "max_attempts": 3, "backoff_s": 0.0}
    )
    assert count[0] == 1


def test_retry_returns_none():
    runner = _make_runner()
    result = runner._step_retry(
        {"steps": [{"type": "wait", "seconds": 0}], "max_attempts": 1, "backoff_s": 0.0}
    )
    assert result is None


# ── failure + retry ───────────────────────────────────────────────────────────


def test_retry_retries_on_failure():
    runner = _make_runner()
    attempt_count = [0]

    def fail_step(step):
        attempt_count[0] += 1
        runner._running = False  # simulate failure

    runner._step_handlers["fail"] = fail_step
    runner._step_retry({"steps": [{"type": "fail"}], "max_attempts": 3, "backoff_s": 0.0})
    assert attempt_count[0] == 3


def test_retry_stops_after_max_attempts():
    runner = _make_runner()
    count = [0]

    def fail_step(step):
        count[0] += 1
        runner._running = False

    runner._step_handlers["fail"] = fail_step
    runner._step_retry({"steps": [{"type": "fail"}], "max_attempts": 2, "backoff_s": 0.0})
    assert count[0] == 2


def test_retry_succeeds_after_one_failure():
    runner = _make_runner()
    call_count = [0]

    def sometimes_fail(step):
        call_count[0] += 1
        if call_count[0] == 1:
            runner._running = False  # fail first
        # second call succeeds (running stays True)

    runner._step_handlers["sometimes_fail"] = sometimes_fail
    runner._step_retry({"steps": [{"type": "sometimes_fail"}], "max_attempts": 3, "backoff_s": 0.0})
    assert call_count[0] == 2  # attempted twice


# ── parameters ────────────────────────────────────────────────────────────────


def test_retry_default_max_attempts_is_3():
    runner = _make_runner()
    count = [0]

    def fail_step(step):
        count[0] += 1
        runner._running = False

    runner._step_handlers["fail"] = fail_step
    runner._step_retry({"steps": [{"type": "fail"}], "backoff_s": 0.0})
    assert count[0] == 3  # default is 3


def test_retry_max_attempts_1_no_retry():
    runner = _make_runner()
    count = [0]

    def fail_step(step):
        count[0] += 1
        runner._running = False

    runner._step_handlers["fail"] = fail_step
    runner._step_retry({"steps": [{"type": "fail"}], "max_attempts": 1, "backoff_s": 0.0})
    assert count[0] == 1
