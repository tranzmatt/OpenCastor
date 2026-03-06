"""Tests for MetricsRegistry.error_rate_histogram() — Issue #421."""

from __future__ import annotations

import time

from castor.metrics import MetricsRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fresh() -> MetricsRegistry:
    """Return a new, isolated MetricsRegistry instance."""
    return MetricsRegistry()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestErrorRateHistogramKeys:
    """The return value must always contain the required top-level keys."""

    def test_returns_buckets_key(self):
        reg = fresh()
        result = reg.error_rate_histogram()
        assert "buckets" in result

    def test_returns_per_provider_key(self):
        reg = fresh()
        result = reg.error_rate_histogram()
        assert "per_provider" in result

    def test_returns_window_s_key(self):
        reg = fresh()
        result = reg.error_rate_histogram()
        assert "window_s" in result

    def test_window_s_matches_argument(self):
        reg = fresh()
        result = reg.error_rate_histogram(window_s=120.0)
        assert result["window_s"] == 120.0

    def test_default_window_s_is_3600(self):
        reg = fresh()
        result = reg.error_rate_histogram()
        assert result["window_s"] == 3600.0


class TestErrorRateHistogramBuckets:
    """Bucket keys and counting logic."""

    def test_bucket_keys_present(self):
        reg = fresh()
        result = reg.error_rate_histogram()
        expected = {"<=0.001", "<=0.01", "<=0.1", "<=1.0", "+Inf"}
        assert set(result["buckets"].keys()) == expected

    def test_plus_inf_equals_number_of_providers_with_recent_errors(self):
        reg = fresh()
        reg.record_provider_error("alpha")
        reg.record_provider_error("beta")
        result = reg.error_rate_histogram()
        assert result["buckets"]["+Inf"] == 2

    def test_buckets_are_cumulative_upper_bounds(self):
        """A provider with a very low rate should appear in all buckets >= its rate."""
        reg = fresh()
        # Record exactly 1 error; rate = 1/3600 ≈ 0.000278 — fits in <=0.001
        reg.record_provider_error("slow_provider")
        result = reg.error_rate_histogram(window_s=3600.0)
        buckets = result["buckets"]
        # Rate ~0.000278 → should appear in <=0.001, <=0.01, <=0.1, <=1.0
        assert buckets["<=0.001"] >= 1
        assert buckets["<=0.01"] >= 1
        assert buckets["<=0.1"] >= 1
        assert buckets["<=1.0"] >= 1

    def test_high_rate_only_in_plus_inf_bucket(self):
        """Provider with rate > 1.0 should only land in +Inf, not the <=1.0 buckets."""
        reg = fresh()
        # Inject 7200 errors in a 1-second window → rate = 7200 errors/s
        now = time.time()
        with reg._lock:
            reg._provider_error_times["hyper"] = [now] * 7200
        result = reg.error_rate_histogram(window_s=1.0)
        buckets = result["buckets"]
        assert buckets["<=0.001"] == 0
        assert buckets["<=0.01"] == 0
        assert buckets["<=0.1"] == 0
        assert buckets["<=1.0"] == 0
        assert buckets["+Inf"] >= 1


class TestErrorRateHistogramPerProvider:
    """per_provider sub-dict structure and values."""

    def test_empty_when_no_errors_recorded(self):
        reg = fresh()
        result = reg.error_rate_histogram()
        assert result["per_provider"] == {}

    def test_provider_with_errors_appears_in_per_provider(self):
        reg = fresh()
        reg.record_provider_error("google")
        result = reg.error_rate_histogram()
        assert "google" in result["per_provider"]

    def test_per_provider_has_required_sub_keys(self):
        reg = fresh()
        reg.record_provider_error("openai")
        info = reg.error_rate_histogram()["per_provider"]["openai"]
        assert "rate" in info
        assert "total_errors" in info
        assert "window_s" in info

    def test_rate_calculation_is_errors_over_window(self):
        reg = fresh()
        # Record 5 errors; rate over window_s=100 should be 0.05
        for _ in range(5):
            reg.record_provider_error("mybot")
        result = reg.error_rate_histogram(window_s=100.0)
        info = result["per_provider"]["mybot"]
        assert abs(info["rate"] - 0.05) < 1e-9
        assert info["total_errors"] == 5
        assert info["window_s"] == 100.0

    def test_old_errors_outside_window_not_counted(self):
        """Timestamps older than window_s should be excluded."""
        reg = fresh()
        old_ts = time.time() - 7200.0  # 2 hours ago
        with reg._lock:
            reg._provider_error_times["stale"] = [old_ts, old_ts]
        result = reg.error_rate_histogram(window_s=3600.0)
        # No recent errors — provider should not appear
        assert "stale" not in result["per_provider"]
        assert result["buckets"]["+Inf"] == 0

    def test_provider_with_zero_recent_errors_not_in_per_provider(self):
        """A provider whose errors all fall outside the window must be absent."""
        reg = fresh()
        old_ts = time.time() - 500.0
        with reg._lock:
            reg._provider_error_times["old_provider"] = [old_ts]
        result = reg.error_rate_histogram(window_s=10.0)
        assert "old_provider" not in result["per_provider"]

    def test_window_s_param_respected_for_filtering(self):
        """Errors within the requested window appear; those outside do not."""
        reg = fresh()
        now = time.time()
        with reg._lock:
            reg._provider_error_times["edge"] = [
                now - 5.0,  # within 60s window
                now - 200.0,  # outside 60s window
            ]
        result = reg.error_rate_histogram(window_s=60.0)
        assert "edge" in result["per_provider"]
        assert result["per_provider"]["edge"]["total_errors"] == 1
