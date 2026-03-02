"""Tests for ProviderPool.warm_providers() — issue #370."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_pool(strategy="round_robin"):
    with patch("castor.providers.get_provider") as mock_factory:
        mock_p1 = MagicMock()
        mock_p1.model_name = "mock-a"
        mock_p1.think.return_value = MagicMock(raw_text="ok", action={"type": "stop"})
        mock_p1.health_check.return_value = {"ok": True, "mode": "mock"}

        mock_p2 = MagicMock()
        mock_p2.model_name = "mock-b"
        mock_p2.think.return_value = MagicMock(raw_text="ok", action={"type": "stop"})
        mock_p2.health_check.return_value = {"ok": False, "mode": "mock", "error": "not ready"}

        mock_factory.side_effect = [mock_p1, mock_p2]

        from castor.providers.pool_provider import ProviderPool

        pool = ProviderPool(
            {
                "pool_strategy": strategy,
                "pool": [
                    {"provider": "a", "model": "m1"},
                    {"provider": "b", "model": "m2"},
                ],
            }
        )
    pool._providers = [mock_p1, mock_p2]
    return pool, mock_p1, mock_p2


# ── Return shape ───────────────────────────────────────────────────────────────


def test_warm_providers_returns_dict():
    pool, p1, p2 = _make_pool()
    result = pool.warm_providers()
    assert isinstance(result, dict)


def test_warm_providers_has_entry_per_provider():
    pool, p1, p2 = _make_pool()
    result = pool.warm_providers()
    assert "0" in result
    assert "1" in result


def test_warm_providers_values_are_bool():
    pool, p1, p2 = _make_pool()
    result = pool.warm_providers()
    for val in result.values():
        assert isinstance(val, bool)


# ── Correctness ────────────────────────────────────────────────────────────────


def test_warm_providers_ok_true_for_healthy():
    pool, p1, p2 = _make_pool()
    result = pool.warm_providers()
    assert result["0"] is True


def test_warm_providers_ok_false_for_unhealthy():
    pool, p1, p2 = _make_pool()
    result = pool.warm_providers()
    assert result["1"] is False


def test_warm_providers_stores_results():
    pool, p1, p2 = _make_pool()
    pool.warm_providers()
    assert hasattr(pool, "_warm_results")
    assert isinstance(pool._warm_results, dict)


def test_warm_providers_calls_health_check_on_each():
    pool, p1, p2 = _make_pool()
    pool.warm_providers()
    p1.health_check.assert_called()
    p2.health_check.assert_called()


# ── Error handling ────────────────────────────────────────────────────────────


def test_warm_providers_handles_exception():
    pool, p1, p2 = _make_pool()
    p1.health_check.side_effect = RuntimeError("provider down")
    result = pool.warm_providers()
    assert result["0"] is False


def test_warm_providers_never_raises():
    pool, p1, p2 = _make_pool()
    p1.health_check.side_effect = Exception("catastrophic failure")
    p2.health_check.side_effect = Exception("also bad")
    result = pool.warm_providers()
    assert isinstance(result, dict)


# ── health_check integration ──────────────────────────────────────────────────


def test_warm_results_in_health_check():
    pool, p1, p2 = _make_pool()
    pool.warm_providers()
    h = pool.health_check()
    assert "warm_results" in h


def test_warm_results_empty_before_warm():
    pool, p1, p2 = _make_pool()
    h = pool.health_check()
    assert "warm_results" in h
    assert isinstance(h["warm_results"], dict)
