"""Tests for LidarDriver.scan_rate() — Issue #403."""

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


@pytest.fixture()
def driver_no_history():
    """LidarDriver with history logging disabled."""
    os.environ["LIDAR_HISTORY_DB"] = "none"
    drv = LidarDriver()
    yield drv
    drv.close()
    os.environ.pop("LIDAR_HISTORY_DB", None)


@pytest.fixture()
def driver_with_history(tmp_path):
    """LidarDriver that has performed several scans (populates history)."""
    db = tmp_path / "lidar_scan_rate.db"
    os.environ["LIDAR_HISTORY_DB"] = str(db)
    drv = LidarDriver()
    # Perform multiple scans to populate the history table.
    for _ in range(5):
        drv.scan()
    yield drv
    drv.close()
    os.environ.pop("LIDAR_HISTORY_DB", None)


# ── Basic return-type tests ───────────────────────────────────────────────────

def test_returns_dict(driver):
    result = driver.scan_rate()
    assert isinstance(result, dict)


def test_has_key_scans_per_second(driver):
    result = driver.scan_rate()
    assert "scans_per_second" in result


def test_has_key_window_s(driver):
    result = driver.scan_rate()
    assert "window_s" in result


def test_has_key_sample_count(driver):
    result = driver.scan_rate()
    assert "sample_count" in result


def test_has_key_mode(driver):
    result = driver.scan_rate()
    assert "mode" in result


# ── Value constraints ─────────────────────────────────────────────────────────

def test_scans_per_second_non_negative(driver):
    result = driver.scan_rate()
    assert result["scans_per_second"] >= 0.0


def test_sample_count_non_negative(driver):
    result = driver.scan_rate()
    assert result["sample_count"] >= 0


def test_window_s_positive(driver):
    result = driver.scan_rate()
    assert result["window_s"] > 0.0


def test_mode_is_str(driver):
    result = driver.scan_rate()
    assert isinstance(result["mode"], str)


# ── No-history / disabled-DB cases ───────────────────────────────────────────

def test_no_history_returns_zero_rate(driver_no_history):
    result = driver_no_history.scan_rate()
    assert result["scans_per_second"] == 0.0


def test_never_raises(driver):
    try:
        driver.scan_rate()
    except Exception as exc:
        pytest.fail(f"scan_rate() raised unexpectedly: {exc}")


# ── Consistency across calls ──────────────────────────────────────────────────

def test_two_calls_consistent_types(driver_with_history):
    r1 = driver_with_history.scan_rate()
    r2 = driver_with_history.scan_rate()
    assert type(r1["scans_per_second"]) is type(r2["scans_per_second"])
    assert type(r1["sample_count"]) is type(r2["sample_count"])
