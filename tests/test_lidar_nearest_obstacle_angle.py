"""Tests for LidarDriver.nearest_obstacle_angle() — Issue #398."""

from __future__ import annotations

import os
import pytest

from castor.drivers.lidar_driver import LidarDriver


@pytest.fixture()
def driver(tmp_path):
    """Create a LidarDriver in mock mode with an isolated history DB."""
    db = tmp_path / "lidar_history.db"
    os.environ["LIDAR_HISTORY_DB"] = str(db)
    drv = LidarDriver()
    yield drv
    drv.close()
    os.environ.pop("LIDAR_HISTORY_DB", None)


# ── Basic return-type tests ───────────────────────────────────────────────────

def test_returns_dict(driver):
    result = driver.nearest_obstacle_angle()
    assert isinstance(result, dict)


def test_has_key_angle_deg(driver):
    result = driver.nearest_obstacle_angle()
    assert "angle_deg" in result


def test_has_key_distance_mm(driver):
    result = driver.nearest_obstacle_angle()
    assert "distance_mm" in result


def test_has_key_mode(driver):
    result = driver.nearest_obstacle_angle()
    assert "mode" in result


def test_mode_is_str(driver):
    result = driver.nearest_obstacle_angle()
    assert isinstance(result["mode"], str)


# ── Mock-mode value tests ─────────────────────────────────────────────────────

def test_mock_angle_deg_is_float_or_none(driver):
    result = driver.nearest_obstacle_angle()
    val = result["angle_deg"]
    assert val is None or isinstance(val, float)


def test_mock_distance_mm_non_negative_or_none(driver):
    result = driver.nearest_obstacle_angle()
    val = result["distance_mm"]
    assert val is None or val >= 0


def test_mock_returns_valid_obstacle(driver):
    """The mock scan always has valid points, so angle_deg should not be None."""
    result = driver.nearest_obstacle_angle()
    assert result["angle_deg"] is not None
    assert result["distance_mm"] is not None


def test_angle_in_0_360_range_when_not_none(driver):
    """angle_deg must be in [0, 360) when present."""
    result = driver.nearest_obstacle_angle()
    angle = result["angle_deg"]
    if angle is not None:
        assert 0.0 <= angle < 360.0


def test_distance_mm_positive_when_not_none(driver):
    result = driver.nearest_obstacle_angle()
    dist = result["distance_mm"]
    if dist is not None:
        assert dist > 0


# ── Stability tests ───────────────────────────────────────────────────────────

def test_multiple_calls_dont_raise(driver):
    for _ in range(5):
        driver.nearest_obstacle_angle()


def test_never_raises(driver):
    try:
        driver.nearest_obstacle_angle()
    except Exception as exc:
        pytest.fail(f"nearest_obstacle_angle() raised unexpectedly: {exc}")


# ── Consistency with obstacles() ──────────────────────────────────────────────

def test_consistent_with_obstacles(driver):
    """distance_mm from nearest_obstacle_angle() should match min_distance_mm
    returned by obstacles() when both are derived from the same scan."""
    # Trigger a scan so _last_scan is populated for both methods.
    driver.scan()
    noa = driver.nearest_obstacle_angle()
    obs = driver.obstacles()

    if noa["distance_mm"] is not None and obs["min_distance_mm"] is not None:
        # They should be equal (both find the global minimum).
        assert abs(noa["distance_mm"] - obs["min_distance_mm"]) < 1.0
