"""Tests for IMUDriver.activity_classifier() — Issue #425."""

import math
import pytest

from castor.drivers.imu_driver import IMUDriver

VALID_ACTIVITIES = {"idle", "walking", "running", "vibrating", "falling"}


@pytest.fixture()
def imu():
    """Return an IMUDriver in mock mode (no hardware required)."""
    return IMUDriver()


# ── Return structure ──────────────────────────────────────────────────────────


def test_returns_correct_keys(imu):
    result = imu.activity_classifier()
    assert set(result.keys()) >= {"activity", "confidence", "variance", "window_n", "mode"}


def test_activity_is_string(imu):
    result = imu.activity_classifier()
    assert isinstance(result["activity"], str)


def test_activity_in_valid_set(imu):
    result = imu.activity_classifier()
    assert result["activity"] in VALID_ACTIVITIES


def test_confidence_is_float(imu):
    result = imu.activity_classifier()
    assert isinstance(result["confidence"], float)


def test_confidence_between_zero_and_one(imu):
    result = imu.activity_classifier()
    assert 0.0 <= result["confidence"] <= 1.0


def test_variance_is_non_negative(imu):
    result = imu.activity_classifier()
    assert result["variance"] >= 0.0


def test_window_n_matches_default(imu):
    result = imu.activity_classifier()
    assert result["window_n"] == 32


def test_window_n_matches_custom(imu):
    result = imu.activity_classifier(window_n=8)
    assert result["window_n"] == 8


def test_mode_is_string(imu):
    result = imu.activity_classifier()
    assert isinstance(result["mode"], str)


# ── Mock mode behaviour ───────────────────────────────────────────────────────


def test_mock_mode_returns_activity(imu):
    """In mock mode the method must return a recognised activity string."""
    result = imu.activity_classifier()
    assert result["activity"] in VALID_ACTIVITIES


def test_mock_activity_default_is_idle(imu):
    assert imu._mock_activity == "idle"
    result = imu.activity_classifier()
    assert result["activity"] == "idle"


def test_mock_activity_attribute_respected(imu):
    imu._mock_activity = "walking"
    result = imu.activity_classifier()
    assert result["activity"] == "walking"
    # Reset for isolation
    imu._mock_activity = "idle"


def test_custom_window_n_8_works(imu):
    result = imu.activity_classifier(window_n=8)
    assert result["activity"] in VALID_ACTIVITIES
    assert result["window_n"] == 8


# ── Robustness ────────────────────────────────────────────────────────────────


def test_never_raises(imu):
    """activity_classifier must not propagate any exception."""
    try:
        imu.activity_classifier()
        imu.activity_classifier(window_n=1)
        imu.activity_classifier(window_n=64)
    except Exception as exc:
        pytest.fail(f"activity_classifier raised unexpectedly: {exc}")


def test_mock_confidence_is_one(imu):
    """Mock mode always reports full confidence."""
    result = imu.activity_classifier()
    assert result["confidence"] == 1.0


def test_all_valid_mock_activities(imu):
    """Cycling through all _mock_activity values should all return valid output."""
    for activity in VALID_ACTIVITIES:
        imu._mock_activity = activity
        result = imu.activity_classifier()
        assert result["activity"] == activity
        assert result["confidence"] == 1.0
        assert result["variance"] >= 0.0
    imu._mock_activity = "idle"


def test_variance_matches_mock_activity(imu):
    """Each mock activity maps to a positive fixed variance."""
    imu._mock_activity = "running"
    result = imu.activity_classifier()
    assert result["variance"] > 0.0


def test_hardware_simulation_via_patched_read(imu, monkeypatch):
    """When read() returns consistent near-1g values, activity should be idle."""
    imu._mode = "hardware"
    imu._bus = object()  # non-None to bypass mock guard

    def _fake_read():
        return {
            "accel_g": {"x": 0.0, "y": 0.0, "z": 1.0},
            "gyro_dps": {"x": 0.0, "y": 0.0, "z": 0.0},
            "mag_uT": None,
            "temp_c": 25.0,
            "mode": "hardware",
            "model": "mpu6050",
        }

    monkeypatch.setattr(imu, "read", _fake_read)
    result = imu.activity_classifier(window_n=16)
    # Consistent 1g readings → near-zero variance → idle
    assert result["activity"] == "idle"
    assert result["variance"] >= 0.0
    assert result["mode"] == "hardware"
