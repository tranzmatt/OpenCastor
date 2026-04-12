"""Tests for castor.safety_benchmark."""

from __future__ import annotations

import pytest

from castor.safety_benchmark import (
    BENCHMARK_SCHEMA_VERSION,
    DEFAULT_THRESHOLDS,
    SafetyBenchmarkReport,
    SafetyBenchmarkResult,
    _bench_bounds_check,
    _bench_confidence_gate,
)


def _make_result(latencies: list[float], threshold: float = 100.0) -> SafetyBenchmarkResult:
    return SafetyBenchmarkResult(
        path="estop",
        iterations=len(latencies),
        latencies_ms=latencies,
        threshold_p95_ms=threshold,
    )


class TestSafetyBenchmarkResult:
    def test_min_ms(self):
        r = _make_result([3.0, 1.0, 2.0])
        assert r.min_ms == pytest.approx(1.0)

    def test_max_ms(self):
        r = _make_result([3.0, 1.0, 2.0])
        assert r.max_ms == pytest.approx(3.0)

    def test_mean_ms(self):
        r = _make_result([2.0, 4.0])
        assert r.mean_ms == pytest.approx(3.0)

    def test_p95_ms_in_range(self):
        latencies = [float(i) for i in range(1, 21)]  # 1..20
        r = _make_result(latencies)
        assert 18.0 <= r.p95_ms <= 20.0

    def test_p99_ms_gte_p95(self):
        latencies = [float(i) for i in range(1, 21)]
        r = _make_result(latencies)
        assert r.p99_ms >= r.p95_ms

    def test_passed_when_p95_below_threshold(self):
        latencies = [1.0] * 20
        r = _make_result(latencies, threshold=5.0)
        assert r.passed is True

    def test_failed_when_p95_exceeds_threshold(self):
        latencies = [200.0] * 20
        r = _make_result(latencies, threshold=100.0)
        assert r.passed is False

    def test_passed_at_exact_threshold(self):
        latencies = [5.0] * 20
        r = _make_result(latencies, threshold=5.0)
        assert r.passed is True

    def test_to_dict_keys(self):
        r = _make_result([1.0, 2.0, 3.0])
        d = r.to_dict()
        assert set(d.keys()) == {"min_ms", "mean_ms", "p95_ms", "p99_ms", "max_ms", "pass"}

    def test_to_dict_pass_field(self):
        latencies = [1.0] * 20
        r = _make_result(latencies, threshold=5.0)
        assert r.to_dict()["pass"] is True


class TestSafetyBenchmarkReport:
    def _make_report(self, all_pass: bool) -> SafetyBenchmarkReport:
        threshold = 100.0
        latencies = [1.0] * 20 if all_pass else [200.0] * 20
        result = SafetyBenchmarkResult(
            path="estop", iterations=20, latencies_ms=latencies, threshold_p95_ms=threshold
        )
        return SafetyBenchmarkReport(
            schema=BENCHMARK_SCHEMA_VERSION,
            generated_at="2026-04-11T00:00:00Z",
            mode="synthetic",
            iterations=20,
            thresholds=dict(DEFAULT_THRESHOLDS),
            results={"estop": result},
        )

    def test_overall_pass_true_when_all_results_pass(self):
        assert self._make_report(all_pass=True).overall_pass is True

    def test_overall_pass_false_when_any_result_fails(self):
        assert self._make_report(all_pass=False).overall_pass is False

    def test_to_dict_has_required_top_level_keys(self):
        d = self._make_report(all_pass=True).to_dict()
        for key in (
            "schema",
            "generated_at",
            "mode",
            "iterations",
            "thresholds",
            "results",
            "overall_pass",
        ):
            assert key in d

    def test_to_dict_results_serialized(self):
        d = self._make_report(all_pass=True).to_dict()
        assert "estop" in d["results"]
        assert "p95_ms" in d["results"]["estop"]


class TestBenchBoundsCheck:
    def test_returns_result_for_bounds_check_path(self):
        result = _bench_bounds_check(config={}, iterations=5)
        assert result.path == "bounds_check"

    def test_iteration_count_matches(self):
        result = _bench_bounds_check(config={}, iterations=7)
        assert result.iterations == 7
        assert len(result.latencies_ms) == 7

    def test_all_latencies_non_negative(self):
        result = _bench_bounds_check(config={}, iterations=10)
        assert all(ms >= 0 for ms in result.latencies_ms)

    def test_threshold_from_defaults(self):
        result = _bench_bounds_check(config={}, iterations=5)
        assert result.threshold_p95_ms == DEFAULT_THRESHOLDS["bounds_check_p95_ms"]

    def test_threshold_from_config_override(self):
        config = {"safety": {"benchmark_thresholds": {"bounds_check_p95_ms": 99.0}}}
        result = _bench_bounds_check(config=config, iterations=5)
        assert result.threshold_p95_ms == pytest.approx(99.0)

    def test_passes_with_default_threshold(self):
        result = _bench_bounds_check(config={}, iterations=20)
        assert result.passed is True


class TestBenchConfidenceGate:
    def test_returns_result_for_confidence_gate_path(self):
        result = _bench_confidence_gate(config={}, iterations=5)
        assert result.path == "confidence_gate"

    def test_iteration_count_matches(self):
        result = _bench_confidence_gate(config={}, iterations=8)
        assert result.iterations == 8
        assert len(result.latencies_ms) == 8

    def test_all_latencies_non_negative(self):
        result = _bench_confidence_gate(config={}, iterations=10)
        assert all(ms >= 0 for ms in result.latencies_ms)

    def test_threshold_from_defaults(self):
        result = _bench_confidence_gate(config={}, iterations=5)
        assert result.threshold_p95_ms == DEFAULT_THRESHOLDS["confidence_gate_p95_ms"]

    def test_passes_with_default_threshold(self):
        result = _bench_confidence_gate(config={}, iterations=20)
        assert result.passed is True
