"""Tests for MetricsRegistry.uptime_histogram() — Issue #431."""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

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


class TestUptimeHistogramKeys:
    """The return value must always contain the required keys."""

    def test_returns_uptime_s_key(self):
        reg = fresh()
        result = reg.uptime_histogram()
        assert "uptime_s" in result

    def test_returns_uptime_m_key(self):
        reg = fresh()
        result = reg.uptime_histogram()
        assert "uptime_m" in result

    def test_returns_uptime_h_key(self):
        reg = fresh()
        result = reg.uptime_histogram()
        assert "uptime_h" in result

    def test_returns_started_at_iso_key(self):
        reg = fresh()
        result = reg.uptime_histogram()
        assert "started_at_iso" in result

    def test_no_unexpected_keys(self):
        reg = fresh()
        result = reg.uptime_histogram()
        assert set(result.keys()) == {"uptime_s", "uptime_m", "uptime_h", "started_at_iso"}


class TestUptimeHistogramValues:
    """Correctness of computed uptime values."""

    def test_uptime_s_is_non_negative(self):
        reg = fresh()
        result = reg.uptime_histogram()
        assert result["uptime_s"] >= 0.0

    def test_uptime_m_equals_uptime_s_over_60(self):
        reg = fresh()
        result = reg.uptime_histogram()
        assert abs(result["uptime_m"] - result["uptime_s"] / 60.0) < 1e-9

    def test_uptime_h_equals_uptime_s_over_3600(self):
        reg = fresh()
        result = reg.uptime_histogram()
        assert abs(result["uptime_h"] - result["uptime_s"] / 3600.0) < 1e-9

    def test_uptime_h_approx_uptime_m_over_60(self):
        reg = fresh()
        result = reg.uptime_histogram()
        assert abs(result["uptime_h"] - result["uptime_m"] / 60.0) < 1e-9

    def test_calling_twice_gives_increasing_uptime_s(self):
        reg = fresh()
        first = reg.uptime_histogram()["uptime_s"]
        time.sleep(0.05)
        second = reg.uptime_histogram()["uptime_s"]
        assert second >= first

    def test_uptime_with_backdated_started_at(self):
        """When _started_at is set to past, uptime should reflect elapsed time."""
        reg = fresh()
        reg._started_at = time.time() - 3600.0  # pretend started 1 hour ago
        result = reg.uptime_histogram()
        assert result["uptime_s"] >= 3600.0 - 1.0  # allow 1s tolerance
        assert result["uptime_h"] >= 1.0 - (1.0 / 3600.0)


class TestUptimeHistogramIso:
    """ISO string format of started_at_iso."""

    def test_started_at_iso_ends_with_z(self):
        reg = fresh()
        result = reg.uptime_histogram()
        assert result["started_at_iso"].endswith("Z")

    def test_started_at_iso_is_valid_datetime(self):
        """started_at_iso should be parseable as an ISO 8601 UTC string."""
        reg = fresh()
        iso = reg.uptime_histogram()["started_at_iso"]
        # Strip trailing Z and parse
        dt = datetime.fromisoformat(iso.rstrip("Z"))
        assert isinstance(dt, datetime)

    def test_started_at_iso_is_utc_not_local(self):
        """The ISO timestamp should match UTC, not wall-clock local time."""
        reg = fresh()
        before = datetime.utcnow()
        iso = reg.uptime_histogram()["started_at_iso"]
        after = datetime.utcnow()
        dt = datetime.fromisoformat(iso.rstrip("Z"))
        # dt should be between before - 1s and after + 1s in UTC
        delta_before = (dt - before).total_seconds()
        delta_after = (after - dt).total_seconds()
        assert delta_before >= -1.0
        assert delta_after >= -1.0
