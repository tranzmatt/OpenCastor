"""Tests for IMUDriver.fall_detection() (#404)."""
import pytest

from castor.drivers.imu_driver import IMUDriver


@pytest.fixture
def imu():
    return IMUDriver()


# ── Basic return shape ────────────────────────────────────────────────────────


def test_fall_detection_returns_dict(imu):
    result = imu.fall_detection()
    assert isinstance(result, dict)


def test_fall_detection_has_required_keys(imu):
    result = imu.fall_detection()
    for key in ("fall_detected", "magnitude_g", "threshold_g", "consecutive_below", "mode"):
        assert key in result, f"Missing key: {key}"


def test_fall_detection_fall_detected_is_bool(imu):
    result = imu.fall_detection()
    assert isinstance(result["fall_detected"], bool)


def test_fall_detection_magnitude_g_is_float(imu):
    result = imu.fall_detection()
    assert isinstance(result["magnitude_g"], float)


def test_fall_detection_threshold_g_is_float(imu):
    result = imu.fall_detection()
    assert isinstance(result["threshold_g"], float)


def test_fall_detection_consecutive_below_is_int(imu):
    result = imu.fall_detection()
    assert isinstance(result["consecutive_below"], int)


def test_fall_detection_mode_is_string(imu):
    result = imu.fall_detection()
    assert isinstance(result["mode"], str)


# ── Mock mode ─────────────────────────────────────────────────────────────────


def test_fall_detection_mock_magnitude_positive(imu):
    """Mock mode simulates ~1g gravity on Z-axis; magnitude must be positive."""
    result = imu.fall_detection()
    assert result["magnitude_g"] > 0.0


def test_fall_detection_mock_no_fall_initially(imu):
    """In mock mode the simulated magnitude (~1g) exceeds the default 0.2g threshold."""
    result = imu.fall_detection()
    assert result["fall_detected"] is False


# ── reset_fall ────────────────────────────────────────────────────────────────


def test_reset_fall_exists(imu):
    assert hasattr(imu, "reset_fall")
    assert callable(imu.reset_fall)


def test_reset_fall_does_not_raise(imu):
    # Should never raise even with no prior fall event
    imu.reset_fall()


def test_reset_fall_resets_consecutive(imu):
    # Manually set the consecutive counter, then verify reset_fall clears it
    imu._fall_consecutive = 5
    imu._fall_detected = True
    imu.reset_fall()
    assert imu._fall_consecutive == 0
    assert imu._fall_detected is False


# ── State ─────────────────────────────────────────────────────────────────────


def test_fall_initially_not_detected(imu):
    assert imu._fall_detected is False


def test_fall_consecutive_starts_zero(imu):
    assert imu._fall_consecutive == 0


# ── Robustness ────────────────────────────────────────────────────────────────


def test_fall_detection_never_raises(imu):
    """Calling fall_detection() must never propagate an exception."""
    for _ in range(5):
        imu.fall_detection()


def test_fall_detection_custom_threshold(imu):
    """Custom threshold is reflected in the returned dict."""
    result = imu.fall_detection(threshold_g=0.5, window_n=2)
    assert result["threshold_g"] == 0.5
