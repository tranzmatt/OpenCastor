"""
tests/test_memory_outcome_timeline.py — Tests for EpisodeMemory.outcome_timeline() (#426).
"""

from __future__ import annotations

import math
import sqlite3
import time

import pytest

from castor.memory import EpisodeMemory


@pytest.fixture
def mem(tmp_path, monkeypatch):
    db = str(tmp_path / "test_outcome_timeline.db")
    monkeypatch.setenv("CASTOR_MEMORY_DB", db)
    return EpisodeMemory(db_path=db)


# 1. outcome_timeline returns a list
def test_outcome_timeline_returns_list(mem):
    result = mem.outcome_timeline("success")
    assert isinstance(result, list)


# 2. empty DB returns all-zero-count buckets (not empty list)
def test_outcome_timeline_empty_db_returns_zero_count_buckets(mem):
    result = mem.outcome_timeline("success", bucket_s=3600.0, window_s=7200.0)
    assert len(result) >= 1
    for item in result:
        assert item["count"] == 0


# 3. each item has bucket_start, bucket_end, count keys
def test_outcome_timeline_items_have_required_keys(mem):
    result = mem.outcome_timeline("ok", bucket_s=3600.0, window_s=7200.0)
    for item in result:
        assert "bucket_start" in item
        assert "bucket_end" in item
        assert "count" in item


# 4. count is a non-negative int
def test_outcome_timeline_count_is_non_negative_int(mem):
    result = mem.outcome_timeline("ok", bucket_s=3600.0, window_s=7200.0)
    for item in result:
        assert isinstance(item["count"], int)
        assert item["count"] >= 0


# 5. bucket span equals bucket_s (approximately)
def test_outcome_timeline_bucket_width_equals_bucket_s(mem):
    bucket_s = 1800.0
    result = mem.outcome_timeline("ok", bucket_s=bucket_s, window_s=7200.0)
    for item in result:
        width = item["bucket_end"] - item["bucket_start"]
        assert abs(width - bucket_s) < 1.0


# 6. total buckets equals ceil(window_s / bucket_s)
def test_outcome_timeline_bucket_count_equals_ceil_division(mem):
    bucket_s = 1800.0
    window_s = 7200.0
    result = mem.outcome_timeline("ok", bucket_s=bucket_s, window_s=window_s)
    expected = math.ceil(window_s / bucket_s)
    assert len(result) == expected


# 7. episodes in correct bucket are counted
def test_outcome_timeline_episode_counted_in_correct_bucket(mem):
    mem.log_episode(instruction="forward", action={}, outcome="success", tags=[])
    result = mem.outcome_timeline("success", bucket_s=3600.0, window_s=7200.0)
    total = sum(item["count"] for item in result)
    assert total == 1


# 8. episodes outside window_s are not counted
def test_outcome_timeline_episodes_outside_window_not_counted(mem):
    old_ts = time.time() - 7200.0
    with sqlite3.connect(mem.db_path) as con:
        con.execute(
            "INSERT INTO episodes (id, ts, instruction, action_json, outcome, source, tags) "
            "VALUES ('old-ep-001', ?, 'old', NULL, 'success', 'test', NULL)",
            (old_ts,),
        )
        con.commit()

    # Window is only 1 hour — old episode should not be counted
    result = mem.outcome_timeline("success", bucket_s=1800.0, window_s=3600.0)
    total = sum(item["count"] for item in result)
    assert total == 0


# 9. partial-match outcome works (LIKE)
def test_outcome_timeline_partial_outcome_match(mem):
    mem.log_episode(instruction="a", action={}, outcome="partial_success", tags=[])
    mem.log_episode(instruction="b", action={}, outcome="full_success", tags=[])
    mem.log_episode(instruction="c", action={}, outcome="failure", tags=[])

    result = mem.outcome_timeline("success", bucket_s=3600.0, window_s=7200.0)
    total = sum(item["count"] for item in result)
    # "partial_success" and "full_success" both contain "success"
    assert total == 2


# 10. bucket_start < bucket_end for every bucket
def test_outcome_timeline_bucket_start_less_than_end(mem):
    result = mem.outcome_timeline("ok", bucket_s=3600.0, window_s=7200.0)
    for item in result:
        assert item["bucket_start"] < item["bucket_end"]


# 11. buckets are time-ordered (bucket_start monotonically increasing)
def test_outcome_timeline_buckets_are_time_ordered(mem):
    result = mem.outcome_timeline("ok", bucket_s=3600.0, window_s=14400.0)
    starts = [item["bucket_start"] for item in result]
    for i in range(1, len(starts)):
        assert starts[i] > starts[i - 1]


# 12. window_s param respected — different window produces different bucket count
def test_outcome_timeline_window_s_param_respected(mem):
    result_short = mem.outcome_timeline("ok", bucket_s=3600.0, window_s=3600.0)
    result_long = mem.outcome_timeline("ok", bucket_s=3600.0, window_s=14400.0)
    # Longer window should produce more buckets
    assert len(result_long) > len(result_short)


# 13. only matching outcome is counted — other outcomes not included
def test_outcome_timeline_counts_only_matching_outcome(mem):
    mem.log_episode(instruction="a", action={}, outcome="success", tags=[])
    mem.log_episode(instruction="b", action={}, outcome="failure", tags=[])
    mem.log_episode(instruction="c", action={}, outcome="success", tags=[])

    result_success = mem.outcome_timeline("success", bucket_s=3600.0, window_s=7200.0)
    result_failure = mem.outcome_timeline("failure", bucket_s=3600.0, window_s=7200.0)

    total_success = sum(item["count"] for item in result_success)
    total_failure = sum(item["count"] for item in result_failure)

    assert total_success == 2
    assert total_failure == 1


# 14. window_s equal to bucket_s returns at least one bucket
def test_outcome_timeline_window_equals_bucket_returns_one_bucket(mem):
    result = mem.outcome_timeline("ok", bucket_s=3600.0, window_s=3600.0)
    assert len(result) >= 1


# 15. never raises on arbitrary/empty input
def test_outcome_timeline_never_raises(mem):
    try:
        mem.outcome_timeline("")
        mem.outcome_timeline("nonexistent_xyz", bucket_s=1.0, window_s=1.0)
        mem.outcome_timeline("ok", bucket_s=3600.0, window_s=86400.0)
    except Exception as exc:
        pytest.fail(f"outcome_timeline raised unexpectedly: {exc}")


# 16. multiple episodes in same bucket all counted
def test_outcome_timeline_multiple_episodes_same_bucket(mem):
    for i in range(5):
        mem.log_episode(instruction=f"step {i}", action={}, outcome="ok", tags=[])

    result = mem.outcome_timeline("ok", bucket_s=3600.0, window_s=7200.0)
    total = sum(item["count"] for item in result)
    assert total == 5
