"""Tests for castor.memory.episodic — EpisodicMemory (#614)."""

from __future__ import annotations

import pytest

from castor.memory.episodic import Episode, EpisodicMemory


@pytest.fixture()
def mem(tmp_path):
    return EpisodicMemory(db_path=tmp_path / "test_episodic.db")


SESSION_LOG = [
    {"role": "user", "content": "go forward"},
    {"role": "assistant", "content": "Moving forward"},
    {"role": "tool", "content": "move(linear=0.5)"},
    {"role": "assistant", "content": ""},
]


def test_record_and_recall(mem):
    ep = mem.record("navigate to charging dock", SESSION_LOG, outcome="success")
    assert isinstance(ep, Episode)
    assert ep.outcome == "success"

    results = mem.recall("navigate")
    assert len(results) == 1
    assert results[0].episode_id == ep.episode_id
    assert results[0].task == "navigate to charging dock"


def test_recall_empty(mem):
    results = mem.recall("nonexistent task xyz")
    assert results == []


def test_recall_only_success(mem):
    mem.record("task A", SESSION_LOG, outcome="failure")
    mem.record("task A", SESSION_LOG, outcome="error")
    results = mem.recall("task A")
    assert results == []


def test_inject_context_empty(mem):
    result = mem.inject_context("unknown task")
    assert result == ""


def test_inject_context_with_episodes(mem):
    mem.record("patrol route", SESSION_LOG, outcome="success")
    result = mem.inject_context("patrol")
    assert result.startswith("[Episodic memory")
    assert "patrol route" in result
    assert "success" in result


def test_in_memory_db():
    """Use ':memory:' path — no filesystem side effects."""
    mem = EpisodicMemory(db_path=":memory:")
    ep = mem.record("test task", SESSION_LOG, outcome="success", tags=["nav", "fast"])
    assert ep.tags == ["nav", "fast"]
    results = mem.recall("test")
    assert len(results) == 1


def test_record_failure_returns_tail(mem):
    long_log = [{"role": "user", "content": f"step {i}"} for i in range(10)]
    ep = mem.record("fail task", long_log, outcome="failure")
    assert len(ep.critical_tool_calls) == 5


def test_context_summary_counts_actions(mem):
    ep = mem.record("greet user", SESSION_LOG, outcome="success")
    # 2 non-empty assistant/tool messages: "Moving forward" + "move(linear=0.5)"
    assert "actions recorded" in ep.context_summary


def test_recall_top_k(mem):
    for _i in range(5):
        mem.record("repeat task", SESSION_LOG, outcome="success")
    results = mem.recall("repeat", top_k=3)
    assert len(results) == 3
