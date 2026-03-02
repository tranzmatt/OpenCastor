"""
tests/test_memory_tag_timeline.py — Tests for EpisodeMemory.tag_timeline() (#401).
"""

from __future__ import annotations

import time

import pytest

from castor.memory import EpisodeMemory


@pytest.fixture
def mem(tmp_path):
    db = str(tmp_path / "test.db")
    return EpisodeMemory(db_path=db)


# 1. tag_timeline returns a list
def test_tag_timeline_returns_list(mem):
    result = mem.tag_timeline("move")
    assert isinstance(result, list)


# 2. list items are dicts
def test_tag_timeline_items_are_dicts(mem):
    result = mem.tag_timeline("move", bucket_s=3600.0, window_s=7200.0)
    for item in result:
        assert isinstance(item, dict)


# 3. each dict has bucket_start, bucket_end, count keys
def test_tag_timeline_dict_has_required_keys(mem):
    result = mem.tag_timeline("move", bucket_s=3600.0, window_s=3600.0)
    for item in result:
        assert "bucket_start" in item
        assert "bucket_end" in item
        assert "count" in item


# 4. count is a non-negative int
def test_tag_timeline_count_is_non_negative_int(mem):
    result = mem.tag_timeline("move", bucket_s=3600.0, window_s=7200.0)
    for item in result:
        assert isinstance(item["count"], int)
        assert item["count"] >= 0


# 5. bucket_start < bucket_end
def test_tag_timeline_bucket_start_less_than_end(mem):
    result = mem.tag_timeline("move", bucket_s=3600.0, window_s=7200.0)
    for item in result:
        assert item["bucket_start"] < item["bucket_end"]


# 6. bucket_end - bucket_start == bucket_s (approximately)
def test_tag_timeline_bucket_width_equals_bucket_s(mem):
    bucket_s = 1800.0
    result = mem.tag_timeline("move", bucket_s=bucket_s, window_s=7200.0)
    for item in result:
        width = item["bucket_end"] - item["bucket_start"]
        assert abs(width - bucket_s) < 1.0


# 7. empty DB returns list of zero-count buckets (not empty list)
def test_tag_timeline_empty_db_returns_zero_count_buckets(mem):
    result = mem.tag_timeline("move", bucket_s=3600.0, window_s=7200.0)
    assert len(result) >= 1
    for item in result:
        assert item["count"] == 0


# 8. after logging episode with tag, count increases
def test_tag_timeline_count_increases_after_log(mem):
    tag = "patrol"
    result_before = mem.tag_timeline(tag, bucket_s=3600.0, window_s=7200.0)
    total_before = sum(item["count"] for item in result_before)

    mem.log_episode(instruction="test", outcome="ok", tags=[tag])

    result_after = mem.tag_timeline(tag, bucket_s=3600.0, window_s=7200.0)
    total_after = sum(item["count"] for item in result_after)

    assert total_after == total_before + 1


# 9. custom bucket_s and window_s accepted
def test_tag_timeline_custom_bucket_and_window(mem):
    result = mem.tag_timeline("move", bucket_s=600.0, window_s=3600.0)
    assert isinstance(result, list)
    assert len(result) >= 1


# 10. never raises on arbitrary input
def test_tag_timeline_never_raises(mem):
    try:
        mem.tag_timeline("")
        mem.tag_timeline("nonexistent_tag_xyz", bucket_s=1.0, window_s=1.0)
        mem.tag_timeline("move", bucket_s=3600.0, window_s=86400.0)
    except Exception as exc:
        pytest.fail(f"tag_timeline raised unexpectedly: {exc}")


# 11. bucket_start values are monotonically increasing
def test_tag_timeline_bucket_starts_monotonically_increasing(mem):
    result = mem.tag_timeline("move", bucket_s=3600.0, window_s=14400.0)
    starts = [item["bucket_start"] for item in result]
    for i in range(1, len(starts)):
        assert starts[i] > starts[i - 1]


# 12. only the correct tag is counted, not other tags
def test_tag_timeline_counts_only_specified_tag(mem):
    mem.log_episode(instruction="a", outcome="ok", tags=["alpha"])
    mem.log_episode(instruction="b", outcome="ok", tags=["beta"])
    mem.log_episode(instruction="c", outcome="ok", tags=["alpha"])

    result_alpha = mem.tag_timeline("alpha", bucket_s=3600.0, window_s=7200.0)
    result_beta = mem.tag_timeline("beta", bucket_s=3600.0, window_s=7200.0)

    total_alpha = sum(item["count"] for item in result_alpha)
    total_beta = sum(item["count"] for item in result_beta)

    assert total_alpha == 2
    assert total_beta == 1


# 13. window_s equal to bucket_s returns at least one bucket
def test_tag_timeline_window_equals_bucket_returns_one_bucket(mem):
    result = mem.tag_timeline("move", bucket_s=3600.0, window_s=3600.0)
    assert len(result) >= 1


# 14. episodes outside the window are not counted
def test_tag_timeline_episodes_outside_window_not_counted(mem):
    # Log an episode 2 hours in the past by directly inserting with old ts
    import sqlite3

    old_ts = time.time() - 7200.0
    with sqlite3.connect(mem.db_path) as con:
        con.execute(
            "INSERT INTO episodes (id, ts, instruction, action_json, outcome, source, tags) "
            "VALUES ('old-ep-001', ?, 'old', NULL, 'ok', 'test', 'patrol')",
            (old_ts,),
        )
        con.commit()

    # Window is only 1 hour — old episode should not be counted
    result = mem.tag_timeline("patrol", bucket_s=1800.0, window_s=3600.0)
    total = sum(item["count"] for item in result)
    assert total == 0
