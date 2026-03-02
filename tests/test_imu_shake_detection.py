"""Tests for IMUDriver.shake_detection() and reset_shake() — issue #369."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reset_singleton():
    import castor.drivers.imu_driver as mod

    mod._singleton = None
    yield
    mod._singleton = None


def _mock_driver():
    with patch("castor.drivers.imu_driver.HAS_SMBUS2", False):
        from castor.drivers.imu_driver import IMUDriver

        return IMUDriver(bus=1, model="auto")


def _hw_driver():
    with patch("castor.drivers.imu_driver.HAS_SMBUS2", False):
        from castor.drivers.imu_driver import IMUDriver

        drv = IMUDriver(bus=1, model="auto")
    drv._mode = "hardware"
    drv._bus = object()
    return drv


def _patch_accel(drv, x=0.0, y=0.0, z=1.0):
    drv.read = lambda: {
        "accel_g": {"x": x, "y": y, "z": z},
        "gyro_dps": {"x": 0.0, "y": 0.0, "z": 0.0},
        "mag_uT": None,
        "temp_c": 25.0,
        "mode": "hardware",
    }


# ── Return shape ────────────────────────────────────────────────────────────


def test_shake_detection_returns_dict():
    drv = _mock_driver()
    assert isinstance(drv.shake_detection(), dict)


def test_shake_detection_required_keys():
    drv = _mock_driver()
    r = drv.shake_detection()
    assert "shaking" in r
    assert "reversals" in r
    assert "axis" in r
    assert "timestamp" in r


# ── Mock mode ────────────────────────────────────────────────────────────────


def test_shake_mock_shaking_false():
    assert _mock_driver().shake_detection()["shaking"] is False


def test_shake_mock_reversals_zero():
    assert _mock_driver().shake_detection()["reversals"] == 0


def test_shake_mock_axis_none():
    assert _mock_driver().shake_detection()["axis"] is None


def test_shake_mock_timestamp_none():
    assert _mock_driver().shake_detection()["timestamp"] is None


# ── State attrs ──────────────────────────────────────────────────────────────


def test_imu_has_shake_history():
    drv = _mock_driver()
    assert hasattr(drv, "_shake_history")
    assert isinstance(drv._shake_history, list)


def test_imu_has_shake_threshold():
    drv = _mock_driver()
    assert hasattr(drv, "_shake_threshold_g")
    assert drv._shake_threshold_g > 0.0


def test_imu_has_min_reversals():
    drv = _mock_driver()
    assert hasattr(drv, "_shake_min_reversals")
    assert drv._shake_min_reversals > 0


# ── reset_shake ──────────────────────────────────────────────────────────────


def test_reset_shake_clears_history():
    drv = _mock_driver()
    drv._shake_history = [(1.0, "x", 1), (1.1, "x", -1)]
    drv.reset_shake()
    assert drv._shake_history == []


def test_reset_shake_on_empty_no_error():
    drv = _mock_driver()
    drv.reset_shake()
    assert drv._shake_history == []


# ── Hardware: below threshold ─────────────────────────────────────────────


def test_hw_no_shake_below_threshold():
    drv = _hw_driver()
    _patch_accel(drv, x=0.5, y=0.5, z=0.5)
    r = drv.shake_detection(threshold_g=2.0)
    assert r["shaking"] is False


# ── Hardware: shake detection ─────────────────────────────────────────────


def test_hw_shake_detected_with_reversals():
    """Inject multiple reversals to trigger a shake."""
    import time

    drv = _hw_driver()
    drv.reset_shake()

    # Inject alternating high-magnitude readings directly into history
    now = time.time()
    drv._shake_history = [
        (now - 0.4, "x", 1),
        (now - 0.3, "x", -1),
        (now - 0.2, "x", 1),
        (now - 0.1, "x", -1),
    ]

    _patch_accel(drv, x=2.5, y=0.0, z=0.0)  # threshold 2.0 g
    r = drv.shake_detection(threshold_g=2.0, min_reversals=3, window_s=1.0)
    assert r["shaking"] is True
    assert r["reversals"] >= 3
    assert r["axis"] == "x"
    assert r["timestamp"] is not None


def test_hw_shake_not_detected_too_few_reversals():
    import time

    drv = _hw_driver()
    drv.reset_shake()
    now = time.time()
    # Only 1 reversal
    drv._shake_history = [
        (now - 0.2, "z", 1),
        (now - 0.1, "z", -1),
    ]
    _patch_accel(drv, x=0.0, y=0.0, z=2.5)
    r = drv.shake_detection(threshold_g=2.0, min_reversals=3, window_s=1.0)
    assert r["shaking"] is False


# ── Hardware: error fallback ──────────────────────────────────────────────


def test_hw_shake_fallback_on_read_error():
    drv = _hw_driver()
    drv.read = lambda: (_ for _ in ()).throw(RuntimeError("sensor fail"))
    r = drv.shake_detection()
    assert r["shaking"] is False
    assert r["axis"] is None
