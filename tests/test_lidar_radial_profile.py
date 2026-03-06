"""Tests for LidarDriver.radial_profile() — issue #428."""

from __future__ import annotations

import pytest


def _make_driver():
    """Return a LidarDriver forced into mock mode (no rplidar)."""
    from castor.drivers.lidar_driver import LidarDriver

    return LidarDriver(port="/dev/null")


# ── Return shape ───────────────────────────────────────────────────────────────


def test_radial_profile_returns_dict():
    d = _make_driver()
    result = d.radial_profile()
    assert isinstance(result, dict)


def test_radial_profile_has_required_keys():
    d = _make_driver()
    result = d.radial_profile()
    for key in ("sectors", "n_sectors", "mode"):
        assert key in result, f"missing key: {key}"


def test_radial_profile_n_sectors_matches_len_sectors():
    d = _make_driver()
    result = d.radial_profile()
    assert result["n_sectors"] == len(result["sectors"])


def test_radial_profile_default_n_sectors_is_36():
    d = _make_driver()
    result = d.radial_profile()
    assert result["n_sectors"] == 36
    assert len(result["sectors"]) == 36


def test_radial_profile_each_sector_has_start_deg():
    d = _make_driver()
    result = d.radial_profile()
    assert all("start_deg" in s for s in result["sectors"])


def test_radial_profile_each_sector_has_end_deg():
    d = _make_driver()
    result = d.radial_profile()
    assert all("end_deg" in s for s in result["sectors"])


def test_radial_profile_each_sector_has_min_dist_mm():
    d = _make_driver()
    result = d.radial_profile()
    assert all("min_dist_mm" in s for s in result["sectors"])


def test_radial_profile_sectors_contiguous():
    """sector[i].end_deg must equal sector[i+1].start_deg."""
    d = _make_driver()
    result = d.radial_profile()
    sectors = result["sectors"]
    for i in range(len(sectors) - 1):
        assert abs(sectors[i]["end_deg"] - sectors[i + 1]["start_deg"]) < 1e-6, (
            f"sectors[{i}].end_deg={sectors[i]['end_deg']} != "
            f"sectors[{i + 1}].start_deg={sectors[i + 1]['start_deg']}"
        )


def test_radial_profile_total_arc_spans_360():
    """First sector starts at 0 and last ends at 360."""
    d = _make_driver()
    result = d.radial_profile()
    sectors = result["sectors"]
    assert sectors[0]["start_deg"] == pytest.approx(0.0)
    assert sectors[-1]["end_deg"] == pytest.approx(360.0)


def test_radial_profile_min_dist_mm_is_float_or_none():
    d = _make_driver()
    result = d.radial_profile()
    for s in result["sectors"]:
        assert s["min_dist_mm"] is None or isinstance(s["min_dist_mm"], (int, float))


def test_radial_profile_custom_n_sectors_4():
    d = _make_driver()
    result = d.radial_profile(n_sectors=4)
    assert result["n_sectors"] == 4
    assert len(result["sectors"]) == 4
    # Each sector should span 90°
    for s in result["sectors"]:
        width = s["end_deg"] - s["start_deg"]
        assert abs(width - 90.0) < 1e-6


def test_radial_profile_n_sectors_1_single_sector():
    d = _make_driver()
    result = d.radial_profile(n_sectors=1)
    assert result["n_sectors"] == 1
    assert len(result["sectors"]) == 1
    assert result["sectors"][0]["start_deg"] == pytest.approx(0.0)
    assert result["sectors"][0]["end_deg"] == pytest.approx(360.0)


def test_radial_profile_mode_is_string():
    d = _make_driver()
    result = d.radial_profile()
    assert isinstance(result["mode"], str)


def test_radial_profile_mock_has_populated_sectors():
    """Mock mode scan has 360 points so most sectors should be populated."""
    d = _make_driver()
    result = d.radial_profile()
    populated = [s for s in result["sectors"] if s["min_dist_mm"] is not None]
    assert len(populated) > 0


def test_radial_profile_min_dist_mm_is_positive():
    """Any populated sector must have a positive min distance."""
    d = _make_driver()
    result = d.radial_profile()
    for s in result["sectors"]:
        if s["min_dist_mm"] is not None:
            assert s["min_dist_mm"] > 0.0


def test_radial_profile_never_raises():
    d = _make_driver()
    try:
        d.radial_profile(n_sectors=72)
    except Exception as exc:
        pytest.fail(f"radial_profile raised: {exc}")
