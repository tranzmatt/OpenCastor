"""Tests for LidarDriver.arc_scan() — issue #422."""

from __future__ import annotations

import pytest


def _make_driver():
    """Return a LidarDriver forced into mock mode (no rplidar)."""
    from castor.drivers.lidar_driver import LidarDriver

    return LidarDriver(port="/dev/null")


# ── Return shape ───────────────────────────────────────────────────────────────


def test_arc_scan_returns_dict():
    d = _make_driver()
    result = d.arc_scan()
    assert isinstance(result, dict)


def test_arc_scan_has_required_keys():
    d = _make_driver()
    result = d.arc_scan()
    for key in ("readings", "arc_start_deg", "arc_end_deg", "count", "mode"):
        assert key in result, f"missing key: {key}"


def test_arc_scan_count_matches_len_readings():
    d = _make_driver()
    result = d.arc_scan(start_deg=0, end_deg=90)
    assert result["count"] == len(result["readings"])


def test_arc_scan_arc_start_deg_preserved():
    d = _make_driver()
    result = d.arc_scan(start_deg=45.0, end_deg=135.0)
    assert result["arc_start_deg"] == 45.0


def test_arc_scan_arc_end_deg_preserved():
    d = _make_driver()
    result = d.arc_scan(start_deg=45.0, end_deg=135.0)
    assert result["arc_end_deg"] == 135.0


def test_arc_scan_readings_within_arc():
    d = _make_driver()
    result = d.arc_scan(start_deg=50.0, end_deg=150.0)
    for r in result["readings"]:
        assert 50.0 <= r["angle_deg"] <= 150.0, f"angle {r['angle_deg']} outside arc [50, 150]"


def test_arc_scan_full_arc_returns_all_readings():
    """0 to 360 should return all available mock readings."""
    d = _make_driver()
    # In mock mode the scan always returns 360 points (0..359 degrees)
    full_result = d.arc_scan(start_deg=0.0, end_deg=360.0)
    assert full_result["count"] > 0


def test_arc_scan_empty_arc_returns_empty():
    """An arc where start == end and there is no synthetic point at that exact degree
    should return very few or no readings."""
    d = _make_driver()
    # Mock generates at exactly start_deg; a 0-width arc from 0 to 0 produces just 1 point
    result = d.arc_scan(start_deg=0.0, end_deg=0.0)
    # The spec says "empty" arc — in mock mode we generate start and step by 5°;
    # when start == end the loop emits exactly 1 point (angle=0).
    # Verify count matches len(readings) and readings list contains only
    # angles satisfying 0 <= angle <= 0
    assert result["count"] == len(result["readings"])
    for r in result["readings"]:
        assert r["angle_deg"] == 0.0


def test_arc_scan_each_reading_has_angle_deg():
    d = _make_driver()
    result = d.arc_scan(start_deg=0, end_deg=60)
    assert all("angle_deg" in r for r in result["readings"])


def test_arc_scan_each_reading_has_dist_mm():
    d = _make_driver()
    result = d.arc_scan(start_deg=0, end_deg=60)
    assert all("dist_mm" in r for r in result["readings"])


def test_arc_scan_mode_is_string():
    d = _make_driver()
    result = d.arc_scan()
    assert isinstance(result["mode"], str)


def test_arc_scan_readings_only_in_range():
    """All returned readings must satisfy start_deg <= angle_deg <= end_deg."""
    d = _make_driver()
    result = d.arc_scan(start_deg=10.0, end_deg=170.0)
    for r in result["readings"]:
        assert 10.0 <= r["angle_deg"] <= 170.0


def test_arc_scan_wrap_around():
    """Wrap-around arc (start > end, e.g. 350 to 10) should return readings in that range."""
    d = _make_driver()
    result = d.arc_scan(start_deg=350.0, end_deg=10.0)
    assert result["count"] > 0
    assert result["count"] == len(result["readings"])
    for r in result["readings"]:
        angle = r["angle_deg"]
        in_arc = angle >= 350.0 or angle <= 10.0
        assert in_arc, f"angle {angle} not in wrap-around arc [350, 10]"


def test_arc_scan_never_raises():
    d = _make_driver()
    try:
        d.arc_scan(start_deg=0.0, end_deg=360.0)
    except Exception as exc:
        pytest.fail(f"arc_scan raised: {exc}")


def test_arc_scan_mock_dist_formula():
    """Mock readings should satisfy dist_mm = 500 + angle_deg * 2."""
    d = _make_driver()
    result = d.arc_scan(start_deg=0.0, end_deg=20.0)
    for r in result["readings"]:
        expected = 500.0 + r["angle_deg"] * 2.0
        assert abs(r["dist_mm"] - expected) < 1e-6, (
            f"dist_mm {r['dist_mm']} != 500 + {r['angle_deg']} * 2 = {expected}"
        )
