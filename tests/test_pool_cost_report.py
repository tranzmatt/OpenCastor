"""Tests for ProviderPool.cost_report() — Issue #427."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from castor.providers.pool_provider import ProviderPool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_pool(n: int = 2) -> ProviderPool:
    """Create a ProviderPool with *n* mock providers."""
    cfg = {
        "pool_strategy": "round_robin",
        "pool": [{"provider": f"p{i}", "model": "m"} for i in range(n)],
    }
    with patch("castor.providers.get_provider", return_value=MagicMock()):
        return ProviderPool(cfg)


def inject_cost(pool: ProviderPool, idx: int, calls: int, cost: float) -> None:
    """Directly write cost entries into the pool's _cost_tracker."""
    pool._cost_tracker[idx] = {
        "tokens_total": float(calls * 100),
        "cost_usd_total": float(cost),
        "calls": float(calls),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCostReportTopLevelKeys:
    def test_returns_providers_key(self) -> None:
        pool = make_pool(2)
        result = pool.cost_report()
        assert "providers" in result

    def test_returns_total_cost_usd_key(self) -> None:
        pool = make_pool(2)
        result = pool.cost_report()
        assert "total_cost_usd" in result

    def test_returns_pool_size_key(self) -> None:
        pool = make_pool(2)
        result = pool.cost_report()
        assert "pool_size" in result

    def test_providers_is_a_list(self) -> None:
        pool = make_pool(2)
        result = pool.cost_report()
        assert isinstance(result["providers"], list)

    def test_pool_size_matches_number_of_providers(self) -> None:
        pool = make_pool(3)
        result = pool.cost_report()
        assert result["pool_size"] == 3

    def test_pool_size_equals_len_providers_list(self) -> None:
        pool = make_pool(2)
        result = pool.cost_report()
        assert result["pool_size"] == len(result["providers"])


class TestCostReportProviderEntryKeys:
    def test_each_entry_has_name(self) -> None:
        pool = make_pool(2)
        for entry in pool.cost_report()["providers"]:
            assert "name" in entry

    def test_each_entry_has_calls(self) -> None:
        pool = make_pool(2)
        for entry in pool.cost_report()["providers"]:
            assert "calls" in entry

    def test_each_entry_has_cost_usd_total(self) -> None:
        pool = make_pool(2)
        for entry in pool.cost_report()["providers"]:
            assert "cost_usd_total" in entry

    def test_each_entry_has_cost_usd_avg_per_call(self) -> None:
        pool = make_pool(2)
        for entry in pool.cost_report()["providers"]:
            assert "cost_usd_avg_per_call" in entry

    def test_each_entry_has_pct_of_total(self) -> None:
        pool = make_pool(2)
        for entry in pool.cost_report()["providers"]:
            assert "pct_of_total" in entry


class TestCostReportValues:
    def test_total_cost_usd_is_sum_of_per_provider_costs(self) -> None:
        pool = make_pool(2)
        inject_cost(pool, 0, calls=5, cost=0.10)
        inject_cost(pool, 1, calls=3, cost=0.06)
        result = pool.cost_report()
        assert result["total_cost_usd"] == pytest.approx(0.16)

    def test_pct_of_total_sums_to_100_when_there_is_spend(self) -> None:
        pool = make_pool(3)
        inject_cost(pool, 0, calls=10, cost=0.50)
        inject_cost(pool, 1, calls=5, cost=0.30)
        inject_cost(pool, 2, calls=2, cost=0.20)
        result = pool.cost_report()
        total_pct = sum(e["pct_of_total"] for e in result["providers"])
        assert total_pct == pytest.approx(100.0)

    def test_avg_per_call_is_zero_when_calls_is_zero(self) -> None:
        pool = make_pool(1)
        # _cost_tracker already initialised to zero calls
        result = pool.cost_report()
        assert result["providers"][0]["cost_usd_avg_per_call"] == 0.0

    def test_pct_of_total_is_zero_when_total_cost_is_zero(self) -> None:
        pool = make_pool(2)
        # No cost injected — all zeros
        result = pool.cost_report()
        for entry in result["providers"]:
            assert entry["pct_of_total"] == 0.0

    def test_avg_per_call_correct_with_calls(self) -> None:
        pool = make_pool(1)
        inject_cost(pool, 0, calls=4, cost=0.04)
        result = pool.cost_report()
        assert result["providers"][0]["cost_usd_avg_per_call"] == pytest.approx(0.01)

    def test_pct_of_total_correct_single_dominant_provider(self) -> None:
        pool = make_pool(2)
        inject_cost(pool, 0, calls=10, cost=0.80)
        inject_cost(pool, 1, calls=2, cost=0.20)
        result = pool.cost_report()
        # Providers list is ordered by pool index; index 0 → 80 %, index 1 → 20 %
        pcts = [e["pct_of_total"] for e in result["providers"]]
        assert pcts[0] == pytest.approx(80.0)
        assert pcts[1] == pytest.approx(20.0)


class TestCostReportEdgeCases:
    def test_pool_size_one(self) -> None:
        pool = make_pool(1)
        inject_cost(pool, 0, calls=7, cost=0.07)
        result = pool.cost_report()
        assert result["pool_size"] == 1
        assert len(result["providers"]) == 1
        assert result["providers"][0]["pct_of_total"] == pytest.approx(100.0)

    def test_pool_size_three(self) -> None:
        pool = make_pool(3)
        result = pool.cost_report()
        assert result["pool_size"] == 3
        assert len(result["providers"]) == 3

    def test_all_zeros_no_activity(self) -> None:
        pool = make_pool(2)
        result = pool.cost_report()
        assert result["total_cost_usd"] == 0.0
        for entry in result["providers"]:
            assert entry["calls"] == 0
            assert entry["cost_usd_total"] == 0.0
            assert entry["cost_usd_avg_per_call"] == 0.0
            assert entry["pct_of_total"] == 0.0
