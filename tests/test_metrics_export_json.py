"""Tests for MetricsRegistry.export_json() — issue #372."""

from __future__ import annotations

import time

import pytest

from castor.metrics import MetricsRegistry


@pytest.fixture()
def reg():
    return MetricsRegistry()


# ── Return shape ───────────────────────────────────────────────────────────────


def test_export_json_returns_dict(reg):
    assert isinstance(reg.export_json(), dict)


def test_export_json_has_counters_key(reg):
    assert "counters" in reg.export_json()


def test_export_json_has_gauges_key(reg):
    assert "gauges" in reg.export_json()


def test_export_json_has_histograms_key(reg):
    assert "histograms" in reg.export_json()


def test_export_json_has_provider_latency_key(reg):
    assert "provider_latency" in reg.export_json()


def test_export_json_has_endpoint_rps_key(reg):
    assert "endpoint_rps" in reg.export_json()


def test_export_json_has_timestamp_key(reg):
    assert "timestamp" in reg.export_json()


# ── Timestamp ─────────────────────────────────────────────────────────────────


def test_export_json_timestamp_is_recent(reg):
    before = time.time()
    result = reg.export_json()
    after = time.time()
    assert before <= result["timestamp"] <= after


# ── Counters ──────────────────────────────────────────────────────────────────


def test_export_json_counters_contains_known_metric(reg):
    result = reg.export_json()
    assert "opencastor_loops_total" in result["counters"]


def test_export_json_counter_increments_reflected(reg):
    c = reg.counter("opencastor_loops_total")
    if c:
        c.inc(robot="test")
    result = reg.export_json()
    counter_data = result["counters"].get("opencastor_loops_total", {})
    total = sum(counter_data.values())
    assert total >= 1


# ── Gauges ────────────────────────────────────────────────────────────────────


def test_export_json_gauges_contains_known_metric(reg):
    result = reg.export_json()
    assert "opencastor_uptime_seconds" in result["gauges"]


def test_export_json_gauge_value_reflected(reg):
    g = reg.gauge("opencastor_uptime_seconds")
    if g:
        g.set(42.0, robot="test")
    result = reg.export_json()
    gauge_data = result["gauges"].get("opencastor_uptime_seconds", {})
    values = list(gauge_data.values())
    assert any(abs(v - 42.0) < 1e-6 for v in values)


# ── Histograms ────────────────────────────────────────────────────────────────


def test_export_json_histograms_contains_loop_duration(reg):
    result = reg.export_json()
    assert "opencastor_loop_duration_ms" in result["histograms"]


def test_export_json_histogram_has_sum_count_buckets(reg):
    h = reg.histogram("opencastor_loop_duration_ms")
    if h:
        h.observe(100.0)
    result = reg.export_json()
    hist_data = result["histograms"].get("opencastor_loop_duration_ms", {})
    assert "sum" in hist_data
    assert "count" in hist_data
    assert "buckets" in hist_data


# ── Provider latency ──────────────────────────────────────────────────────────


def test_export_json_provider_latency_after_observation(reg):
    reg.record_provider_latency("google", 250.0)
    result = reg.export_json()
    assert "google" in result["provider_latency"]


def test_export_json_provider_latency_has_percentile_keys(reg):
    reg.record_provider_latency("test_provider", 100.0)
    result = reg.export_json()
    data = result["provider_latency"].get("test_provider", {})
    assert "p50" in data
    assert "p95" in data
    assert "p99" in data


# ── Endpoint RPS ──────────────────────────────────────────────────────────────


def test_export_json_endpoint_rps_after_record(reg):
    reg.record_request("/api/command")
    result = reg.export_json()
    assert "/api/command" in result["endpoint_rps"]


# ── JSON serialisability ──────────────────────────────────────────────────────


def test_export_json_is_json_serialisable(reg):
    import json

    reg.record_provider_latency("google", 200.0)
    reg.record_request("/api/test")
    result = reg.export_json()
    # Should not raise
    serialised = json.dumps(result)
    assert len(serialised) > 0
