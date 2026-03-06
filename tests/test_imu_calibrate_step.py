"""Tests for IMUDriver.calibrate_step_threshold() (#391)."""

import pytest

from castor.drivers.imu_driver import IMUDriver


@pytest.fixture
def imu():
    return IMUDriver()


# ── basic return shape ────────────────────────────────────────────────────────


def test_calibrate_returns_dict(imu):
    result = imu.calibrate_step_threshold()
    assert isinstance(result, dict)


def test_calibrate_has_required_keys(imu):
    result = imu.calibrate_step_threshold()
    for key in ("noise_floor_g", "threshold_g", "calibrated", "samples", "mode"):
        assert key in result, f"missing key: {key}"


def test_calibrate_calibrated_is_bool(imu):
    result = imu.calibrate_step_threshold()
    assert isinstance(result["calibrated"], bool)


def test_calibrate_mode_is_string(imu):
    result = imu.calibrate_step_threshold()
    assert isinstance(result["mode"], str)


def test_calibrate_samples_non_negative(imu):
    result = imu.calibrate_step_threshold()
    assert result["samples"] >= 0


def test_calibrate_threshold_g_is_float_or_none(imu):
    result = imu.calibrate_step_threshold()
    assert result["threshold_g"] is None or isinstance(result["threshold_g"], float)


# ── mock mode always calibrates ───────────────────────────────────────────────


def test_calibrate_mock_mode_returns_calibrated_true(imu):
    if imu._mode == "mock":
        result = imu.calibrate_step_threshold()
        assert result["calibrated"] is True


def test_calibrate_mock_sets_calibrated_flag(imu):
    if imu._mode == "mock":
        imu.calibrate_step_threshold()
        assert imu._calibrated is True


def test_calibrate_mock_noise_floor_is_numeric(imu):
    if imu._mode == "mock":
        result = imu.calibrate_step_threshold()
        assert isinstance(result["noise_floor_g"], float)
        assert result["noise_floor_g"] > 0


def test_calibrate_mock_threshold_above_noise_floor(imu):
    if imu._mode == "mock":
        result = imu.calibrate_step_threshold()
        assert result["threshold_g"] >= result["noise_floor_g"]


# ── parameter passing ─────────────────────────────────────────────────────────


def test_calibrate_custom_calibration_factor(imu):
    if imu._mode == "mock":
        result = imu.calibrate_step_threshold(calibration_factor=3.0)
        assert result["threshold_g"] == pytest.approx(result["noise_floor_g"] * 3.0)


def test_calibrate_custom_n_idle(imu):
    if imu._mode == "mock":
        result = imu.calibrate_step_threshold(n_idle=5)
        assert result["samples"] >= 0  # mock returns the passed n_idle as samples


# ── updates _step_threshold ───────────────────────────────────────────────────


def test_calibrate_updates_step_threshold(imu):
    imu.calibrate_step_threshold()
    # After calibration, threshold should be set (may differ from original in hardware mode)
    assert imu._step_threshold > 0


def test_calibrate_threshold_used_in_step_counter(imu):
    imu.calibrate_step_threshold()
    result = imu.step_counter()
    assert result["threshold_g"] == pytest.approx(imu._step_threshold)


# ── state flags ───────────────────────────────────────────────────────────────


def test_calibrate_sets_calibrated_attr(imu):
    imu.calibrate_step_threshold()
    assert hasattr(imu, "_calibrated")
    assert isinstance(imu._calibrated, bool)


def test_calibrate_initially_not_calibrated(imu):
    # Fresh IMU should not be calibrated yet
    assert imu._calibrated is False


# ── never raises ─────────────────────────────────────────────────────────────


def test_calibrate_never_raises(imu):
    try:
        imu.calibrate_step_threshold()
    except Exception as exc:
        pytest.fail(f"calibrate_step_threshold raised: {exc}")
