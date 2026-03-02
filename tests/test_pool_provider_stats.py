"""Tests for ProviderPool.provider_stats() (Issue #405)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from castor.providers.base import Thought
from castor.providers.pool_provider import ProviderPool


def _make_pool(cfg_extra=None):
    """Build a ProviderPool with two mocked providers."""
    cfg = {
        "pool_strategy": "round_robin",
        "pool_fallback": True,
        "pool": [{"provider": "mock1"}, {"provider": "mock2"}],
    }
    if cfg_extra:
        cfg.update(cfg_extra)
    p1 = MagicMock()
    p1.model_name = "mock1"
    p2 = MagicMock()
    p2.model_name = "mock2"
    with patch("castor.providers.get_provider", side_effect=[p1, p2]):
        pool = ProviderPool(cfg)
    return pool, p1, p2


# ------------------------------------------------------------------
# Return type and structure
# ------------------------------------------------------------------


def test_provider_stats_returns_dict():
    """provider_stats() should return a dict."""
    pool, _, _ = _make_pool()
    stats = pool.provider_stats()
    assert isinstance(stats, dict)


def test_provider_stats_has_required_keys():
    """provider_stats() should have 'providers', 'strategy', and 'pool_size' keys."""
    pool, _, _ = _make_pool()
    stats = pool.provider_stats()
    assert "providers" in stats
    assert "strategy" in stats
    assert "pool_size" in stats


def test_providers_is_a_list():
    """The 'providers' value should be a list."""
    pool, _, _ = _make_pool()
    stats = pool.provider_stats()
    assert isinstance(stats["providers"], list)


def test_each_provider_stat_has_required_fields():
    """Each provider entry should have all required stat fields."""
    pool, _, _ = _make_pool()
    stats = pool.provider_stats()
    required_fields = {
        "name", "index", "calls", "cost_usd_total",
        "tokens_total", "avg_latency_ms", "degraded", "cb_open",
    }
    for entry in stats["providers"]:
        for field in required_fields:
            assert field in entry, f"Missing field '{field}' in provider stat: {entry}"


def test_pool_size_matches_number_of_providers():
    """pool_size should equal the number of providers in the pool."""
    pool, _, _ = _make_pool()
    stats = pool.provider_stats()
    assert stats["pool_size"] == 2


def test_strategy_matches_configured_strategy():
    """strategy should reflect the configured pool_strategy."""
    pool, _, _ = _make_pool({"pool_strategy": "random"})
    stats = pool.provider_stats()
    assert stats["strategy"] == "random"


def test_strategy_defaults_to_round_robin():
    """strategy should default to 'round_robin'."""
    pool, _, _ = _make_pool()
    stats = pool.provider_stats()
    assert stats["strategy"] == "round_robin"


def test_calls_starts_at_zero():
    """calls should start at 0 before any think() calls."""
    pool, _, _ = _make_pool()
    stats = pool.provider_stats()
    for entry in stats["providers"]:
        assert entry["calls"] == 0


def test_degraded_starts_false():
    """degraded should be False for all providers initially."""
    pool, _, _ = _make_pool()
    stats = pool.provider_stats()
    for entry in stats["providers"]:
        assert entry["degraded"] is False


def test_cb_open_starts_false():
    """cb_open should be False for all providers initially."""
    pool, _, _ = _make_pool()
    stats = pool.provider_stats()
    for entry in stats["providers"]:
        assert entry["cb_open"] is False


def test_cost_usd_total_starts_at_zero():
    """cost_usd_total should start at 0.0 before any think() calls."""
    pool, _, _ = _make_pool()
    stats = pool.provider_stats()
    for entry in stats["providers"]:
        assert entry["cost_usd_total"] == pytest.approx(0.0)


def test_provider_names_match_model_names():
    """Provider 'name' fields should match the configured model_name attributes."""
    pool, _, _ = _make_pool()
    stats = pool.provider_stats()
    names = [entry["name"] for entry in stats["providers"]]
    assert "mock1" in names
    assert "mock2" in names


def test_provider_indices_are_sequential():
    """Provider 'index' fields should be sequential integers starting from 0."""
    pool, _, _ = _make_pool()
    stats = pool.provider_stats()
    indices = [entry["index"] for entry in stats["providers"]]
    assert indices == list(range(len(stats["providers"])))
