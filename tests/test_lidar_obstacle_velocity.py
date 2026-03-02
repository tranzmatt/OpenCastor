"""Tests for LidarDriver.obstacles_with_velocity() (#393)."""

import time

import pytest

from castor.drivers.lidar_driver import LidarDriver


@pytest.fixture
def lidar():
    return LidarDriver(port="/dev/null")


# ── basic return shape ────────────────────────────────────────────────────────

def test_obstacles_with_velocity_returns_dict(lidar):
    result = lidar.obstacles_with_velocity()
    assert isinstance(result, dict)


def test_obstacles_with_velocity_has_required_keys(lidar):
    result = lidar.obstacles_with_velocity()
    for key in ("sectors", "min_distance_mm", "nearest_angle_deg", "mode"):
        assert key in result, f"missing key: {key}"


def test_obstacles_with_velocity_sectors_is_dict(lidar):
    result = lidar.obstacles_with_velocity()
    assert isinstance(result["sectors"], dict)


def test_obstacles_with_velocity_has_four_sectors(lidar):
    result = lidar.obstacles_with_velocity()
    sectors = result["sectors"]
    assert set(sectors.keys()) == {"front", "right", "rear", "left"}


def test_obstacles_with_velocity_each_sector_has_dist_and_vel(lidar):
    result = lidar.obstacles_with_velocity()
    for sector_data in result["sectors"].values():
        assert "dist_mm" in sector_data
        assert "velocity_mm_s" in sector_data


def test_obstacles_with_velocity_mode_is_string(lidar):
    result = lidar.obstacles_with_velocity()
    assert isinstance(result["mode"], str)


# ── velocity values ───────────────────────────────────────────────────────────

def test_velocity_is_float_or_none(lidar):
    result = lidar.obstacles_with_velocity()
    for sector_data in result["sectors"].values():
        vel = sector_data["velocity_mm_s"]
        assert isinstance(vel, float)


def test_first_call_velocity_zero(lidar):
    """First call has no previous snapshot — all velocities should be 0.0."""
    lidar._vel_prev_sectors.clear()
    result = lidar.obstacles_with_velocity()
    for sector_data in result["sectors"].values():
        assert sector_data["velocity_mm_s"] == pytest.approx(0.0)


def test_velocity_non_negative_or_negative(lidar):
    """Velocity can be positive (receding) or negative (approaching)."""
    lidar.obstacles_with_velocity()  # first call
    time.sleep(0.01)
    result = lidar.obstacles_with_velocity()  # second call
    for sector_data in result["sectors"].values():
        assert isinstance(sector_data["velocity_mm_s"], float)


# ── persistence across calls ──────────────────────────────────────────────────

def test_vel_prev_sectors_populated_after_call(lidar):
    lidar.obstacles_with_velocity()
    assert len(lidar._vel_prev_sectors) > 0


def test_vel_prev_sectors_has_correct_keys(lidar):
    lidar.obstacles_with_velocity()
    assert set(lidar._vel_prev_sectors.keys()) == {"front", "right", "rear", "left"}


def test_vel_prev_sectors_is_tuple(lidar):
    lidar.obstacles_with_velocity()
    for val in lidar._vel_prev_sectors.values():
        assert isinstance(val, tuple)
        assert len(val) == 2  # (dist_mm, timestamp)


# ── never raises ─────────────────────────────────────────────────────────────

def test_obstacles_with_velocity_never_raises(lidar):
    try:
        lidar.obstacles_with_velocity()
    except Exception as exc:
        pytest.fail(f"obstacles_with_velocity raised: {exc}")


def test_obstacles_with_velocity_multiple_calls_never_raises(lidar):
    for _ in range(5):
        lidar.obstacles_with_velocity()
