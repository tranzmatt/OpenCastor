"""Tests for LidarDriver.zone_velocity() — issue #366."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reset_singleton():
    import castor.drivers.lidar_driver as mod

    mod._singleton = None
    yield
    mod._singleton = None


def _mock_driver():
    with patch("castor.drivers.lidar_driver.HAS_RPLIDAR", False):
        from castor.drivers.lidar_driver import LidarDriver

        return LidarDriver()


# ── Return shape ──────────────────────────────────────────────────────────────


def test_zone_velocity_returns_dict():
    drv = _mock_driver()
    assert isinstance(drv.zone_velocity(), dict)


def test_zone_velocity_required_keys():
    drv = _mock_driver()
    r = drv.zone_velocity()
    for key in ("zone", "velocity_m_s", "samples", "window_s", "direction"):
        assert key in r


def test_zone_velocity_default_zone_is_front():
    drv = _mock_driver()
    assert drv.zone_velocity()["zone"] == "front"


def test_zone_velocity_samples_zero_no_history():
    drv = _mock_driver()
    r = drv.zone_velocity()
    assert r["samples"] == 0
    assert r["velocity_m_s"] == 0.0


def test_zone_velocity_direction_stationary_no_history():
    drv = _mock_driver()
    assert drv.zone_velocity()["direction"] == "stationary"


# ── Zone parameter ────────────────────────────────────────────────────────────


def test_zone_velocity_accepts_left():
    drv = _mock_driver()
    r = drv.zone_velocity(zone="left")
    assert r["zone"] == "left"


def test_zone_velocity_accepts_right():
    drv = _mock_driver()
    r = drv.zone_velocity(zone="right")
    assert r["zone"] == "right"


def test_zone_velocity_accepts_rear():
    drv = _mock_driver()
    r = drv.zone_velocity(zone="rear")
    assert r["zone"] == "rear"


def test_zone_velocity_unknown_zone_returns_stationary():
    drv = _mock_driver()
    r = drv.zone_velocity(zone="banana")
    assert r["direction"] == "stationary"
    assert r["velocity_m_s"] == 0.0


# ── With synthetic scan history ────────────────────────────────────────────────


def _make_scan_entry(timestamp, angle_deg, distance_mm):
    return {
        "timestamp": timestamp,
        "points": [{"angle": angle_deg, "distance": distance_mm, "quality": 15}],
    }


def test_zone_velocity_approaching_returns_negative():
    """Objects getting closer → negative slope → approaching."""
    drv = _mock_driver()
    now = time.time()
    history = [
        _make_scan_entry(now - 2.0, 0.0, 2000),  # 2.0 m, 2s ago
        _make_scan_entry(now - 1.0, 0.0, 1500),  # 1.5 m, 1s ago
        _make_scan_entry(now - 0.0, 0.0, 1000),  # 1.0 m, now
    ]
    drv.get_scan_history = lambda window_s, limit: history
    r = drv.zone_velocity(zone="front", window_s=3.0)
    assert r["direction"] == "approaching"
    assert r["velocity_m_s"] < 0.0


def test_zone_velocity_receding_returns_positive():
    """Objects moving away → positive slope → receding."""
    drv = _mock_driver()
    now = time.time()
    history = [
        _make_scan_entry(now - 2.0, 0.0, 1000),  # 1.0 m, 2s ago
        _make_scan_entry(now - 1.0, 0.0, 1500),  # 1.5 m, 1s ago
        _make_scan_entry(now, 0.0, 2000),  # 2.0 m, now
    ]
    drv.get_scan_history = lambda window_s, limit: history
    r = drv.zone_velocity(zone="front", window_s=3.0)
    assert r["direction"] == "receding"
    assert r["velocity_m_s"] > 0.0


def test_zone_velocity_window_s_reflected_in_result():
    drv = _mock_driver()
    r = drv.zone_velocity(window_s=5.0)
    assert r["window_s"] == 5.0


def test_zone_velocity_single_scan_entry_returns_zero():
    drv = _mock_driver()
    now = time.time()
    drv.get_scan_history = lambda window_s, limit: [_make_scan_entry(now, 0.0, 1000)]
    r = drv.zone_velocity()
    assert r["samples"] == 0
    assert r["velocity_m_s"] == 0.0


def test_zone_velocity_never_raises():
    drv = _mock_driver()
    drv.get_scan_history = lambda **kw: (_ for _ in ()).throw(RuntimeError("db error"))
    r = drv.zone_velocity()
    assert r["velocity_m_s"] == 0.0
    assert r["direction"] == "stationary"
