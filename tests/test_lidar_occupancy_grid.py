"""Tests for LidarDriver.occupancy_grid() — issue #374."""

from __future__ import annotations

import pytest


def _make_driver():
    from castor.drivers.lidar_driver import LidarDriver

    return LidarDriver(port="/dev/null")


# ── Return shape ───────────────────────────────────────────────────────────────


def test_occupancy_grid_returns_dict():
    d = _make_driver()
    result = d.occupancy_grid()
    assert isinstance(result, dict)


def test_occupancy_grid_has_grid_key():
    d = _make_driver()
    result = d.occupancy_grid()
    assert "grid" in result


def test_occupancy_grid_has_origin_key():
    d = _make_driver()
    result = d.occupancy_grid()
    assert "origin" in result


def test_occupancy_grid_has_size_m_key():
    d = _make_driver()
    result = d.occupancy_grid()
    assert "size_m" in result


def test_occupancy_grid_has_resolution_m_key():
    d = _make_driver()
    result = d.occupancy_grid()
    assert "resolution_m" in result


def test_occupancy_grid_has_cells_key():
    d = _make_driver()
    result = d.occupancy_grid()
    assert "cells" in result


def test_occupancy_grid_has_mode_key():
    d = _make_driver()
    result = d.occupancy_grid()
    assert "mode" in result


# ── Grid shape ─────────────────────────────────────────────────────────────────


def test_occupancy_grid_default_size():
    d = _make_driver()
    result = d.occupancy_grid()
    assert result["size_m"] == 5.0


def test_occupancy_grid_default_resolution():
    d = _make_driver()
    result = d.occupancy_grid()
    assert result["resolution_m"] == 0.05


def test_occupancy_grid_cells_dimension():
    d = _make_driver()
    result = d.occupancy_grid(size_m=5.0, resolution_m=0.05)
    expected_cells = int(5.0 / 0.05)  # 100
    assert result["cells"] == expected_cells


def test_occupancy_grid_grid_is_list_of_lists():
    d = _make_driver()
    result = d.occupancy_grid()
    assert isinstance(result["grid"], list)
    assert all(isinstance(row, list) for row in result["grid"])


def test_occupancy_grid_grid_rows_match_cells():
    d = _make_driver()
    result = d.occupancy_grid()
    cells = result["cells"]
    assert len(result["grid"]) == cells


def test_occupancy_grid_grid_cols_match_cells():
    d = _make_driver()
    result = d.occupancy_grid()
    cells = result["cells"]
    for row in result["grid"]:
        assert len(row) == cells


def test_occupancy_grid_origin_is_list():
    d = _make_driver()
    result = d.occupancy_grid()
    assert isinstance(result["origin"], list)
    assert len(result["origin"]) == 2


# ── Mock mode ─────────────────────────────────────────────────────────────────


def test_occupancy_grid_mock_mode_all_zeros():
    d = _make_driver()
    result = d.occupancy_grid()
    assert result["mode"] == "mock"
    for row in result["grid"]:
        assert all(v == 0.0 for v in row)


# ── Custom params ─────────────────────────────────────────────────────────────


def test_occupancy_grid_custom_size():
    d = _make_driver()
    result = d.occupancy_grid(size_m=2.0, resolution_m=0.1)
    assert result["size_m"] == 2.0
    assert result["resolution_m"] == 0.1
    assert result["cells"] == 20


def test_occupancy_grid_never_raises():
    d = _make_driver()
    try:
        d.occupancy_grid(size_m=0.1, resolution_m=0.1)
    except Exception as exc:
        pytest.fail(f"occupancy_grid raised: {exc}")
