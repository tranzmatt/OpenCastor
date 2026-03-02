"""
tests/test_memory_find_by_outcome.py — Tests for EpisodeMemory.find_by_outcome() (#407).
"""

from __future__ import annotations

import pytest

from castor.memory import EpisodeMemory


@pytest.fixture
def mem(tmp_path):
    db = str(tmp_path / "test.db")
    return EpisodeMemory(db_path=db)


# 1. returns a list
def test_find_by_outcome_returns_list(mem):
    result = mem.find_by_outcome("ok")
    assert isinstance(result, list)


# 2. empty DB returns []
def test_find_by_outcome_empty_db_returns_empty(mem):
    result = mem.find_by_outcome("ok")
    assert result == []


# 3. after logging episode with outcome="ok", find_by_outcome("ok") finds it
def test_find_by_outcome_finds_logged_episode(mem):
    mem.log_episode(instruction="go forward", outcome="ok")
    result = mem.find_by_outcome("ok")
    assert len(result) >= 1


# 4. exact=True matches only exact outcome
def test_find_by_outcome_exact_match_only(mem):
    mem.log_episode(instruction="go", outcome="ok")
    mem.log_episode(instruction="go", outcome="ok_partial")
    mem.log_episode(instruction="go", outcome="not_ok")

    result = mem.find_by_outcome("ok", exact=True)
    outcomes = [ep["outcome"] for ep in result]
    assert all(o == "ok" for o in outcomes)
    assert "ok_partial" not in outcomes
    assert "not_ok" not in outcomes


# 5. exact=False (default) does partial match
def test_find_by_outcome_partial_match_default(mem):
    mem.log_episode(instruction="a", outcome="ok")
    mem.log_episode(instruction="b", outcome="ok_partial")
    mem.log_episode(instruction="c", outcome="error")

    result = mem.find_by_outcome("ok")
    outcomes = [ep["outcome"] for ep in result]
    assert "ok" in outcomes
    assert "ok_partial" in outcomes
    assert "error" not in outcomes


# 6. limit parameter respected
def test_find_by_outcome_limit_respected(mem):
    for i in range(10):
        mem.log_episode(instruction=f"ep {i}", outcome="ok")

    result = mem.find_by_outcome("ok", limit=3)
    assert len(result) <= 3


# 7. result items are dicts with standard episode keys
def test_find_by_outcome_result_items_are_dicts_with_keys(mem):
    mem.log_episode(instruction="test", outcome="ok")
    result = mem.find_by_outcome("ok")
    assert len(result) >= 1
    ep = result[0]
    assert isinstance(ep, dict)
    for key in ("id", "ts", "instruction", "outcome", "source"):
        assert key in ep


# 8. multiple outcomes trackable
def test_find_by_outcome_multiple_outcomes(mem):
    mem.log_episode(instruction="a", outcome="ok")
    mem.log_episode(instruction="b", outcome="error")
    mem.log_episode(instruction="c", outcome="timeout")

    ok_results = mem.find_by_outcome("ok", exact=True)
    err_results = mem.find_by_outcome("error", exact=True)
    timeout_results = mem.find_by_outcome("timeout", exact=True)

    assert len(ok_results) == 1
    assert len(err_results) == 1
    assert len(timeout_results) == 1


# 9. case sensitivity works as SQL LIKE works (case-insensitive for ASCII by default in SQLite)
def test_find_by_outcome_case_behavior(mem):
    mem.log_episode(instruction="a", outcome="OK")
    mem.log_episode(instruction="b", outcome="ok")

    # SQLite LIKE is case-insensitive for ASCII letters by default
    result = mem.find_by_outcome("ok", exact=False)
    outcomes = [ep["outcome"] for ep in result]
    # Both "OK" and "ok" should be found since SQLite LIKE is case-insensitive for ASCII
    assert "ok" in outcomes


# 10. never raises on arbitrary input
def test_find_by_outcome_never_raises(mem):
    try:
        mem.find_by_outcome("")
        mem.find_by_outcome("nonexistent_outcome_xyz")
        mem.find_by_outcome("ok", limit=1, exact=True)
        mem.find_by_outcome("ok", limit=1000, exact=False)
    except Exception as exc:
        pytest.fail(f"find_by_outcome raised unexpectedly: {exc}")


# 11. ordered by ts DESC (most recent first)
def test_find_by_outcome_ordered_by_ts_desc(mem):
    import time

    mem.log_episode(instruction="first", outcome="ok")
    time.sleep(0.01)
    mem.log_episode(instruction="second", outcome="ok")
    time.sleep(0.01)
    mem.log_episode(instruction="third", outcome="ok")

    result = mem.find_by_outcome("ok", exact=True)
    ts_values = [ep["ts"] for ep in result]
    for i in range(1, len(ts_values)):
        assert ts_values[i] <= ts_values[i - 1]


# 12. exact=True with no matching outcome returns []
def test_find_by_outcome_exact_no_match_returns_empty(mem):
    mem.log_episode(instruction="a", outcome="ok_extra")
    result = mem.find_by_outcome("ok", exact=True)
    assert result == []


# 13. result includes tags as a list
def test_find_by_outcome_result_includes_tags(mem):
    mem.log_episode(instruction="tagged", outcome="ok", tags=["patrol", "indoor"])
    result = mem.find_by_outcome("ok", exact=True)
    assert len(result) >= 1
    ep = result[0]
    assert isinstance(ep.get("tags"), list)
    assert "patrol" in ep["tags"]
    assert "indoor" in ep["tags"]
