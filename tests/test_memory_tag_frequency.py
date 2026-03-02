"""Tests for EpisodeMemory.tag_frequency() — issue #367."""

from __future__ import annotations

import pytest

from castor.memory import EpisodeMemory


@pytest.fixture()
def mem(tmp_path):
    db = str(tmp_path / "mem.db")
    m = EpisodeMemory(db_path=db, max_episodes=0)
    m.log_episode(instruction="go", raw_thought="ok", action={"type": "move"})
    m.log_episode(instruction="go", raw_thought="ok", action={"type": "move"})
    m.log_episode(instruction="stop", raw_thought="ok", action={"type": "stop"})
    return m


# ── Return shape ───────────────────────────────────────────────────────────────


def test_tag_frequency_returns_list(mem):
    result = mem.tag_frequency()
    assert isinstance(result, list)


def test_tag_frequency_entries_are_dicts(mem):
    result = mem.tag_frequency()
    for entry in result:
        assert isinstance(entry, dict)


def test_tag_frequency_required_keys(mem):
    result = mem.tag_frequency()
    for entry in result:
        assert "tag" in entry
        assert "count" in entry
        assert "frequency" in entry


# ── Empty store ────────────────────────────────────────────────────────────────


def test_tag_frequency_empty_store(tmp_path):
    m = EpisodeMemory(db_path=str(tmp_path / "empty.db"), max_episodes=0)
    assert m.tag_frequency() == []


# ── Count correctness ──────────────────────────────────────────────────────────


def test_tag_frequency_counts_correct(mem):
    result = mem.tag_frequency()
    tags = {r["tag"]: r["count"] for r in result}
    assert tags.get("move") == 2
    assert tags.get("stop") == 1


def test_tag_frequency_sorted_descending(mem):
    result = mem.tag_frequency()
    counts = [r["count"] for r in result]
    assert counts == sorted(counts, reverse=True)


def test_tag_frequency_top_k_respected(mem):
    result = mem.tag_frequency(top_k=1)
    assert len(result) <= 1


def test_tag_frequency_top_k_default_ten(tmp_path):
    m = EpisodeMemory(db_path=str(tmp_path / "topk.db"), max_episodes=0)
    for i in range(15):
        m.log_episode(instruction="x", raw_thought="ok", action={"type": f"type_{i}"})
    result = m.tag_frequency()
    assert len(result) <= 10


def test_tag_frequency_frequencies_sum_leq_one(mem):
    result = mem.tag_frequency()
    total_freq = sum(r["frequency"] for r in result)
    assert total_freq <= 1.0 + 1e-9


def test_tag_frequency_frequency_is_float(mem):
    for r in mem.tag_frequency():
        assert isinstance(r["frequency"], float)


# ── Window filter ──────────────────────────────────────────────────────────────


def test_tag_frequency_window_s_zero_returns_empty(mem):
    # window_s=0 → cutoff = now → no episodes within 0 seconds
    result = mem.tag_frequency(window_s=0.0)
    assert result == []


def test_tag_frequency_large_window_includes_all(mem):
    result = mem.tag_frequency(window_s=86400.0)
    total = sum(r["count"] for r in result)
    assert total == 3


# ── Error safety ───────────────────────────────────────────────────────────────


def test_tag_frequency_never_raises(tmp_path):
    m = EpisodeMemory(db_path=str(tmp_path / "safe.db"), max_episodes=0)
    result = m.tag_frequency(window_s=-1.0)
    assert isinstance(result, list)
