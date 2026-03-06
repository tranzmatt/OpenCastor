"""Tests for MetricsRegistry.provider_error_histogram() — Issue #397."""

import threading

import pytest

from castor.metrics import MetricsRegistry, get_registry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def reg():
    """Return a fresh MetricsRegistry (not the singleton)."""
    return MetricsRegistry()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProviderErrorHistogramInstantiation:
    def test_initial_error_counts_dict_exists(self, reg):
        """_provider_error_counts is initialised as an empty dict."""
        assert hasattr(reg, "_provider_error_counts")
        assert isinstance(reg._provider_error_counts, dict)
        assert reg._provider_error_counts == {}

    def test_provider_error_histogram_callable(self, reg):
        """provider_error_histogram() is callable on a fresh registry."""
        assert callable(reg.provider_error_histogram)

    def test_returns_dict_with_correct_keys(self, reg):
        """Return value has 'buckets' and 'per_provider' keys."""
        result = reg.provider_error_histogram()
        assert "buckets" in result
        assert "per_provider" in result

    def test_empty_registry_all_zero(self, reg):
        """With no errors recorded every bucket is 0 and per_provider is empty."""
        result = reg.provider_error_histogram()
        assert result["per_provider"] == {}
        for val in result["buckets"].values():
            assert val == 0


class TestProviderErrorHistogramKeys:
    def test_bucket_labels_present(self, reg):
        """Buckets dict contains all expected labels."""
        expected = {"<=1", "<=5", "<=10", "<=50", "<=100", "<=500", "<=1000", "+Inf"}
        result = reg.provider_error_histogram()
        assert set(result["buckets"].keys()) == expected

    def test_bucket_count(self, reg):
        """Exactly 8 bucket entries (7 thresholds + +Inf)."""
        result = reg.provider_error_histogram()
        assert len(result["buckets"]) == 8


class TestProviderErrorHistogramRecording:
    def test_record_provider_error_updates_per_provider(self, reg):
        """record_provider_error() increments per_provider counts."""
        reg.record_provider_error("google")
        result = reg.provider_error_histogram()
        assert result["per_provider"]["google"] == 1

    def test_multiple_errors_same_provider(self, reg):
        """Multiple calls for the same provider accumulate correctly."""
        for _ in range(7):
            reg.record_provider_error("anthropic", "timeout")
        result = reg.provider_error_histogram()
        assert result["per_provider"]["anthropic"] == 7

    def test_different_providers_tracked_separately(self, reg):
        """Different providers maintain independent counts."""
        reg.record_provider_error("google")
        reg.record_provider_error("google")
        reg.record_provider_error("ollama")
        result = reg.provider_error_histogram()
        assert result["per_provider"]["google"] == 2
        assert result["per_provider"]["ollama"] == 1

    def test_plus_inf_equals_total_providers_with_errors(self, reg):
        """The +Inf bucket equals the number of distinct providers that have errors."""
        reg.record_provider_error("alpha")
        reg.record_provider_error("beta")
        reg.record_provider_error("gamma")
        result = reg.provider_error_histogram()
        assert result["buckets"]["+Inf"] == 3

    def test_buckets_non_decreasing(self, reg):
        """Bucket values must be monotonically non-decreasing."""
        reg.record_provider_error("p1")  # count=1  → fits in <=1
        reg.record_provider_error("p2")
        reg.record_provider_error("p2")  # count=2  → fits in <=5 but not <=1
        reg.record_provider_error("p3")
        for _ in range(10):
            reg.record_provider_error("p3")  # count=11 → fits in <=50 but not <=10

        result = reg.provider_error_histogram()
        ordered_labels = ["<=1", "<=5", "<=10", "<=50", "<=100", "<=500", "<=1000"]
        values = [result["buckets"][lbl] for lbl in ordered_labels]
        for i in range(len(values) - 1):
            assert values[i] <= values[i + 1], (
                f"Bucket {ordered_labels[i]}={values[i]} > {ordered_labels[i + 1]}={values[i + 1]}"
            )

    def test_bucket_counts_reflect_thresholds(self, reg):
        """Providers with errors ≤ threshold are counted in that bucket."""
        # p1: 1 error, p2: 5 errors, p3: 6 errors
        reg.record_provider_error("p1")
        for _ in range(5):
            reg.record_provider_error("p2")
        for _ in range(6):
            reg.record_provider_error("p3")

        result = reg.provider_error_histogram()
        # <=1: only p1 (count=1 ≤ 1)
        assert result["buckets"]["<=1"] == 1
        # <=5: p1 (1 ≤ 5) and p2 (5 ≤ 5)
        assert result["buckets"]["<=5"] == 2
        # <=10: all three (1, 5, 6 all ≤ 10)
        assert result["buckets"]["<=10"] == 3


class TestProviderErrorHistogramSingleton:
    def test_get_registry_singleton_has_method(self):
        """The global singleton also exposes provider_error_histogram()."""
        reg = get_registry()
        assert callable(reg.provider_error_histogram)

    def test_singleton_returns_dict(self):
        """get_registry().provider_error_histogram() returns the expected shape."""
        reg = get_registry()
        result = reg.provider_error_histogram()
        assert isinstance(result, dict)
        assert "buckets" in result
        assert "per_provider" in result

    def test_thread_safety(self, reg):
        """Concurrent record_provider_error calls don't corrupt counts."""
        errors = []

        def _record():
            try:
                for _ in range(100):
                    reg.record_provider_error("concurrent_provider")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_record) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        result = reg.provider_error_histogram()
        assert result["per_provider"]["concurrent_provider"] == 500
