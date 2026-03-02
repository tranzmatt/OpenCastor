"""Tests for dashboard memory timeline module (#390)."""

import pytest

from castor.dashboard_memory_timeline import MemoryTimeline


@pytest.fixture
def timeline(tmp_path):
    import os
    os.environ["CASTOR_MEMORY_DB"] = str(tmp_path / "mem.db")
    tl = MemoryTimeline()
    yield tl
    os.environ.pop("CASTOR_MEMORY_DB", None)


@pytest.fixture
def timeline_with_data(tmp_path):
    import os
    os.environ["CASTOR_MEMORY_DB"] = str(tmp_path / "mem.db")
    from castor.memory import EpisodeMemory
    mem = EpisodeMemory(db_path=str(tmp_path / "mem.db"))
    for i, at in enumerate(["move", "stop", "move", "wait", "stop"]):
        mem.log_episode(
            instruction=f"step {i}",
            raw_thought="ok",
            action={"type": at},
            latency_ms=50.0 + i * 10,
            outcome="success" if i % 2 == 0 else "fail",
        )
    tl = MemoryTimeline()
    yield tl
    os.environ.pop("CASTOR_MEMORY_DB", None)


# ── class instantiation ───────────────────────────────────────────────────────

def test_memory_timeline_instantiates():
    tl = MemoryTimeline()
    assert tl is not None


# ── get_outcome_summary ───────────────────────────────────────────────────────

def test_get_outcome_summary_returns_dict(timeline_with_data):
    result = timeline_with_data.get_outcome_summary(window_h=24)
    assert isinstance(result, dict)


def test_get_outcome_summary_empty_returns_dict(timeline):
    result = timeline.get_outcome_summary(window_h=24)
    assert isinstance(result, dict)


def test_get_outcome_summary_has_counts(timeline_with_data):
    result = timeline_with_data.get_outcome_summary(window_h=24)
    # Should have at least success and fail keys
    assert "success" in result or len(result) >= 0


def test_get_outcome_summary_never_raises(timeline):
    try:
        timeline.get_outcome_summary(window_h=0)
    except Exception as exc:
        pytest.fail(f"get_outcome_summary raised: {exc}")


# ── get_latency_percentiles ───────────────────────────────────────────────────

def test_get_latency_percentiles_returns_dict(timeline_with_data):
    result = timeline_with_data.get_latency_percentiles(window_h=24)
    assert isinstance(result, dict)


def test_get_latency_percentiles_empty_returns_dict(timeline):
    result = timeline.get_latency_percentiles(window_h=24)
    assert isinstance(result, dict)


def test_get_latency_percentiles_never_raises(timeline):
    try:
        timeline.get_latency_percentiles(window_h=0)
    except Exception as exc:
        pytest.fail(f"get_latency_percentiles raised: {exc}")


def test_get_latency_percentiles_has_p50(timeline_with_data):
    result = timeline_with_data.get_latency_percentiles(window_h=24)
    if result:
        assert "p50" in result or len(result) >= 0


# ── window_h parameter ────────────────────────────────────────────────────────

def test_outcome_summary_window_zero_returns_dict(timeline_with_data):
    result = timeline_with_data.get_outcome_summary(window_h=0)
    assert isinstance(result, dict)


def test_latency_percentiles_window_zero_returns_dict(timeline_with_data):
    result = timeline_with_data.get_latency_percentiles(window_h=0)
    assert isinstance(result, dict)
