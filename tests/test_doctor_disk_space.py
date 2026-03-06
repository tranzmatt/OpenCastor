"""Tests for castor doctor check_disk_space — issue #371."""

from __future__ import annotations

from unittest.mock import patch


def _usage(total, used):
    import shutil

    free = total - used
    return shutil.disk_usage.__class__.__mro__  # just to trigger import
    # Use namedtuple-compatible object
    from collections import namedtuple

    DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])
    return DiskUsage(total=total, used=used, free=free)


def _make_usage(total, used):
    from collections import namedtuple

    DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])
    return DiskUsage(total=total, used=used, free=total - used)


# ── Return shape ───────────────────────────────────────────────────────────────


def test_check_disk_space_returns_tuple():
    from castor.doctor import check_disk_space

    with patch("shutil.disk_usage", return_value=_make_usage(100 * 1024**3, 50 * 1024**3)):
        result = check_disk_space()
    assert isinstance(result, tuple)
    assert len(result) == 3


def test_check_disk_space_name_is_disk_space():
    from castor.doctor import check_disk_space

    with patch("shutil.disk_usage", return_value=_make_usage(100 * 1024**3, 50 * 1024**3)):
        ok, name, detail = check_disk_space()
    assert name == "Disk space"


# ── OK paths ───────────────────────────────────────────────────────────────────


def test_check_disk_space_ok_at_50_percent():
    from castor.doctor import check_disk_space

    with patch("shutil.disk_usage", return_value=_make_usage(100 * 1024**3, 50 * 1024**3)):
        ok, name, detail = check_disk_space()
    assert ok is True


def test_check_disk_space_ok_at_89_percent():
    from castor.doctor import check_disk_space

    total = 100 * 1024**3
    used = int(total * 0.89)
    with patch("shutil.disk_usage", return_value=_make_usage(total, used)):
        ok, name, detail = check_disk_space()
    assert ok is True


def test_check_disk_space_detail_contains_percent(tmp_path):
    from castor.doctor import check_disk_space

    with patch("shutil.disk_usage", return_value=_make_usage(100 * 1024**3, 50 * 1024**3)):
        ok, name, detail = check_disk_space()
    assert "%" in detail


# ── Fail paths ─────────────────────────────────────────────────────────────────


def test_check_disk_space_fail_at_90_percent():
    from castor.doctor import check_disk_space

    total = 100 * 1024**3
    used = int(total * 0.90)
    with patch("shutil.disk_usage", return_value=_make_usage(total, used)):
        ok, name, detail = check_disk_space()
    assert ok is False


def test_check_disk_space_fail_at_95_percent():
    from castor.doctor import check_disk_space

    total = 100 * 1024**3
    used = int(total * 0.95)
    with patch("shutil.disk_usage", return_value=_make_usage(total, used)):
        ok, name, detail = check_disk_space()
    assert ok is False


def test_check_disk_space_fail_detail_warns_full():
    from castor.doctor import check_disk_space

    total = 100 * 1024**3
    used = int(total * 0.95)
    with patch("shutil.disk_usage", return_value=_make_usage(total, used)):
        ok, name, detail = check_disk_space()
    assert "full" in detail.lower() or "90" in detail


# ── Exception handling ─────────────────────────────────────────────────────────


def test_check_disk_space_handles_exception():
    from castor.doctor import check_disk_space

    with patch("shutil.disk_usage", side_effect=OSError("no such path")):
        ok, name, detail = check_disk_space()
    assert ok is False
    assert "no such path" in detail


# ── Integration: included in run_all_checks ────────────────────────────────────


def test_check_disk_space_in_run_all_checks():
    from castor.doctor import run_all_checks

    with patch("shutil.disk_usage", return_value=_make_usage(100 * 1024**3, 50 * 1024**3)):
        results = run_all_checks()
    names = [r[1] for r in results]
    assert "Disk space" in names
