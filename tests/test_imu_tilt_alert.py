"""Tests for IMUDriver.tilt_alert() — Issue #430."""

import pytest

from castor.drivers.imu_driver import IMUDriver


@pytest.fixture()
def imu():
    """Return an IMUDriver in mock mode (no hardware required)."""
    return IMUDriver()


# ── Return structure ──────────────────────────────────────────────────────────


def test_returns_correct_keys(imu):
    result = imu.tilt_alert()
    assert set(result.keys()) >= {
        "alert",
        "pitch_deg",
        "roll_deg",
        "max_pitch_deg",
        "max_roll_deg",
        "mode",
    }


def test_alert_is_bool(imu):
    result = imu.tilt_alert()
    assert isinstance(result["alert"], bool)


def test_pitch_deg_is_float(imu):
    result = imu.tilt_alert()
    assert isinstance(result["pitch_deg"], float)


def test_roll_deg_is_float(imu):
    result = imu.tilt_alert()
    assert isinstance(result["roll_deg"], float)


def test_max_pitch_deg_preserved_default(imu):
    result = imu.tilt_alert()
    assert result["max_pitch_deg"] == 30.0


def test_max_roll_deg_preserved_default(imu):
    result = imu.tilt_alert()
    assert result["max_roll_deg"] == 30.0


def test_custom_thresholds_preserved(imu):
    result = imu.tilt_alert(max_pitch_deg=15.0, max_roll_deg=20.0)
    assert result["max_pitch_deg"] == 15.0
    assert result["max_roll_deg"] == 20.0


def test_mode_is_string(imu):
    result = imu.tilt_alert()
    assert isinstance(result["mode"], str)


# ── Alert logic ───────────────────────────────────────────────────────────────


def test_alert_false_when_within_bounds(imu, monkeypatch):
    """Pitch/roll within thresholds → alert False."""
    monkeypatch.setattr(
        imu,
        "orientation",
        lambda: {"pitch_deg": 5.0, "roll_deg": 3.0, "yaw_deg": 0.0, "mode": "mock"},
    )
    result = imu.tilt_alert(max_pitch_deg=30.0, max_roll_deg=30.0)
    assert result["alert"] is False


def test_alert_true_when_pitch_exceeds_threshold(imu, monkeypatch):
    """Pitch beyond threshold → alert True."""
    monkeypatch.setattr(
        imu,
        "orientation",
        lambda: {"pitch_deg": 45.0, "roll_deg": 2.0, "yaw_deg": 0.0, "mode": "mock"},
    )
    result = imu.tilt_alert(max_pitch_deg=30.0, max_roll_deg=30.0)
    assert result["alert"] is True
    assert result["pitch_deg"] == 45.0


def test_alert_true_when_roll_exceeds_threshold(imu, monkeypatch):
    """Roll beyond threshold → alert True."""
    monkeypatch.setattr(
        imu,
        "orientation",
        lambda: {"pitch_deg": 2.0, "roll_deg": 50.0, "yaw_deg": 0.0, "mode": "mock"},
    )
    result = imu.tilt_alert(max_pitch_deg=30.0, max_roll_deg=30.0)
    assert result["alert"] is True
    assert result["roll_deg"] == 50.0


def test_alert_true_negative_pitch(imu, monkeypatch):
    """Negative pitch beyond threshold (absolute value check) → alert True."""
    monkeypatch.setattr(
        imu,
        "orientation",
        lambda: {"pitch_deg": -40.0, "roll_deg": 0.0, "yaw_deg": 0.0, "mode": "mock"},
    )
    result = imu.tilt_alert(max_pitch_deg=30.0, max_roll_deg=30.0)
    assert result["alert"] is True


def test_alert_false_exact_threshold(imu, monkeypatch):
    """Values exactly equal to threshold must NOT trigger alert (strict >)."""
    monkeypatch.setattr(
        imu,
        "orientation",
        lambda: {"pitch_deg": 30.0, "roll_deg": 30.0, "yaw_deg": 0.0, "mode": "mock"},
    )
    result = imu.tilt_alert(max_pitch_deg=30.0, max_roll_deg=30.0)
    # 30.0 > 30.0 is False
    assert result["alert"] is False


def test_pitch_roll_values_in_result(imu, monkeypatch):
    """Returned pitch/roll values must match orientation() output."""
    monkeypatch.setattr(
        imu,
        "orientation",
        lambda: {"pitch_deg": 12.5, "roll_deg": -8.3, "yaw_deg": 0.0, "mode": "mock"},
    )
    result = imu.tilt_alert()
    assert result["pitch_deg"] == 12.5
    assert result["roll_deg"] == -8.3


# ── Mock mode baseline ────────────────────────────────────────────────────────


def test_mock_mode_no_alert_by_default(imu):
    """Mock orientation returns 0 degrees → no alert with default 30° thresholds."""
    result = imu.tilt_alert()
    assert result["alert"] is False


# ── Robustness ────────────────────────────────────────────────────────────────


def test_never_raises(imu):
    """tilt_alert must not propagate any exception."""
    try:
        imu.tilt_alert()
        imu.tilt_alert(max_pitch_deg=5.0, max_roll_deg=5.0)
        imu.tilt_alert(max_pitch_deg=90.0, max_roll_deg=90.0)
    except Exception as exc:
        pytest.fail(f"tilt_alert raised unexpectedly: {exc}")
