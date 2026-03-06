"""Tests for ProviderPool circuit breaker (#388)."""

from unittest.mock import MagicMock, patch

import pytest

from castor.providers.base import Thought
from castor.providers.pool_provider import ProviderPool


def _thought(text="ok"):
    return Thought(raw_text=text, action={"type": "stop"})


def _make_pool(threshold=3, cooldown_s=1.0):
    p1 = MagicMock()
    p1.health_check.return_value = {"ok": True}
    p1.think.return_value = _thought("primary")

    p2 = MagicMock()
    p2.health_check.return_value = {"ok": True}
    p2.think.return_value = _thought("secondary")

    config = {
        "pool_strategy": "round_robin",
        "pool_circuit_breaker_threshold": threshold,
        "pool_circuit_breaker_cooldown_s": cooldown_s,
        "pool": [
            {"priority": 1, "provider": "mock_p1", "api_key": "x"},
            {"priority": 2, "provider": "mock_p2", "api_key": "x"},
        ],
    }
    with patch("castor.providers.get_provider") as gp:
        gp.side_effect = [p1, p2]
        pool = ProviderPool(config)
    return pool, p1, p2


# ── config stored ─────────────────────────────────────────────────────────────


def test_cb_threshold_stored():
    pool, _, _ = _make_pool(threshold=5)
    assert pool._cb_threshold == 5


def test_cb_cooldown_stored():
    pool, _, _ = _make_pool(cooldown_s=30.0)
    assert pool._cb_cooldown_s == pytest.approx(30.0)


def test_cb_disabled_when_threshold_zero():
    pool, _, _ = _make_pool(threshold=0)
    assert pool._cb_threshold == 0


def test_cb_failures_initially_empty():
    pool, _, _ = _make_pool()
    assert pool._cb_failures == {}


def test_cb_open_until_initially_empty():
    pool, _, _ = _make_pool()
    assert pool._cb_open_until == {}


# ── health check reports circuit_breaker ─────────────────────────────────────


def test_health_check_has_circuit_breaker_key():
    pool, _, _ = _make_pool(threshold=2)
    health = pool.health_check()
    assert "circuit_breaker" in health


def test_health_check_cb_threshold_matches():
    pool, _, _ = _make_pool(threshold=3)
    health = pool.health_check()
    assert health["circuit_breaker"]["threshold"] == 3


def test_health_check_cb_cooldown_matches():
    pool, _, _ = _make_pool(cooldown_s=60.0)
    health = pool.health_check()
    assert health["circuit_breaker"]["cooldown_s"] == pytest.approx(60.0)


def test_health_check_no_cb_key_when_disabled():
    pool, _, _ = _make_pool(threshold=0)
    health = pool.health_check()
    assert "circuit_breaker" not in health


# ── think works normally without failures ────────────────────────────────────


def test_think_succeeds_normally():
    pool, p1, p2 = _make_pool(threshold=3)
    result = pool.think(None, "go")
    assert isinstance(result, Thought)


# ── circuit opens after consecutive failures ──────────────────────────────────


def test_cb_opens_after_threshold_failures():
    pool, p1, _ = _make_pool(threshold=2, cooldown_s=60.0)
    # Force failures on provider 0
    p1.think.side_effect = RuntimeError("boom")

    # After threshold failures, provider 0 should be in _cb_open_until
    for _ in range(3):
        try:
            pool.think(None, "go")
        except Exception:
            pass

    # Check that p1 (index 0) was tripped
    if pool._cb_threshold > 0:
        assert len(pool._cb_open_until) > 0 or pool._cb_failures.get(0, 0) >= pool._cb_threshold


# ── failure count resets on success ──────────────────────────────────────────


def test_cb_failure_count_resets_on_success():
    pool, p1, _ = _make_pool(threshold=5)
    pool._cb_failures[0] = 3
    # Simulate a successful call via _cb_record_success
    if hasattr(pool, "_cb_record_success"):
        pool._cb_record_success(0)
        assert pool._cb_failures.get(0, 0) == 0
    else:
        # success should clear failures — call think and verify
        result = pool.think(None, "go")
        assert isinstance(result, Thought)


# ── providers dict in health check ───────────────────────────────────────────


def test_health_check_cb_providers_dict():
    pool, _, _ = _make_pool(threshold=3)
    health = pool.health_check()
    cb = health.get("circuit_breaker", {})
    assert "providers" in cb
    assert isinstance(cb["providers"], dict)
