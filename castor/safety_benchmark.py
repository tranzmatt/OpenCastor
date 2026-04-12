"""Safety path latency benchmark for EU AI Act evidence (RCAN #859).

Measures the four safety-critical software paths and writes a signed JSON
artifact. Designed to be run in CI (synthetic mode, default) or against a
live robot (--live flag, affects estop and full_pipeline only).
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from typing import Any

BENCHMARK_SCHEMA_VERSION = "rcan-safety-benchmark-v1"

DEFAULT_THRESHOLDS: dict[str, float] = {
    "estop_p95_ms": 100.0,
    "bounds_check_p95_ms": 5.0,
    "confidence_gate_p95_ms": 2.0,
    "full_pipeline_p95_ms": 50.0,
}


def _get_threshold(config: dict, key: str) -> float:
    """Return threshold from config override or DEFAULT_THRESHOLDS."""
    overrides = config.get("safety", {}).get("benchmark_thresholds", {})
    return float(overrides.get(key, DEFAULT_THRESHOLDS[key]))


@dataclass
class SafetyBenchmarkResult:
    path: str  # "estop" | "bounds_check" | "confidence_gate" | "full_pipeline"
    iterations: int
    latencies_ms: list[float]
    threshold_p95_ms: float

    @property
    def min_ms(self) -> float:
        return min(self.latencies_ms)

    @property
    def max_ms(self) -> float:
        return max(self.latencies_ms)

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.latencies_ms)

    @property
    def p95_ms(self) -> float:
        q = statistics.quantiles(self.latencies_ms, n=100)
        return q[min(94, len(q) - 1)]

    @property
    def p99_ms(self) -> float:
        q = statistics.quantiles(self.latencies_ms, n=100)
        return q[min(98, len(q) - 1)]

    @property
    def passed(self) -> bool:
        return self.p95_ms <= self.threshold_p95_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_ms": round(self.min_ms, 4),
            "mean_ms": round(self.mean_ms, 4),
            "p95_ms": round(self.p95_ms, 4),
            "p99_ms": round(self.p99_ms, 4),
            "max_ms": round(self.max_ms, 4),
            "pass": self.passed,
        }


@dataclass
class SafetyBenchmarkReport:
    schema: str
    generated_at: str
    mode: str  # "synthetic" | "live"
    iterations: int
    thresholds: dict[str, float]
    results: dict[str, SafetyBenchmarkResult]

    @property
    def overall_pass(self) -> bool:
        return all(r.passed for r in self.results.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "generated_at": self.generated_at,
            "mode": self.mode,
            "iterations": self.iterations,
            "thresholds": dict(self.thresholds),
            "results": {k: v.to_dict() for k, v in self.results.items()},
            "overall_pass": self.overall_pass,
        }


def _bench_bounds_check(config: dict, iterations: int) -> SafetyBenchmarkResult:
    """Benchmark BoundsChecker evaluation (pure computation, always synthetic)."""
    from castor.safety.bounds import BoundsResult, BoundsStatus

    threshold = _get_threshold(config, "bounds_check_p95_ms")
    latencies: list[float] = []

    action_results = [
        BoundsResult(status=BoundsStatus.OK, details="within limits", margin=0.5),
        BoundsResult(status=BoundsStatus.OK, details="within limits", margin=0.3),
    ]

    for _ in range(iterations):
        t0 = time.perf_counter()
        BoundsResult.combine(action_results)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)

    return SafetyBenchmarkResult(
        path="bounds_check",
        iterations=iterations,
        latencies_ms=latencies,
        threshold_p95_ms=threshold,
    )


def _bench_confidence_gate(config: dict, iterations: int) -> SafetyBenchmarkResult:
    """Benchmark ConfidenceGateEnforcer evaluation (pure computation, always synthetic)."""
    from castor.confidence_gate import ConfidenceGate, ConfidenceGateEnforcer

    threshold = _get_threshold(config, "confidence_gate_p95_ms")
    latencies: list[float] = []

    enforcer = ConfidenceGateEnforcer(
        [
            ConfidenceGate(scope="control", min_confidence=0.75, on_fail="block"),
        ]
    )

    for _ in range(iterations):
        t0 = time.perf_counter()
        enforcer.evaluate("control", 0.8)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)

    return SafetyBenchmarkResult(
        path="confidence_gate",
        iterations=iterations,
        latencies_ms=latencies,
        threshold_p95_ms=threshold,
    )


def _bench_estop(config: dict, iterations: int, live: bool) -> SafetyBenchmarkResult:
    """Benchmark ESTOP software path."""
    raise NotImplementedError("implemented in Task 2")


def _bench_full_pipeline(config: dict, iterations: int, live: bool) -> SafetyBenchmarkResult:
    """Benchmark full SafetyLayer pipeline."""
    raise NotImplementedError("implemented in Task 2")


def run_safety_benchmark(
    config: dict,
    iterations: int = 20,
    live: bool = False,
) -> SafetyBenchmarkReport:
    """Run all four safety path benchmarks. Returns a SafetyBenchmarkReport."""
    raise NotImplementedError("implemented in Task 2")
