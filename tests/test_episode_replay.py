"""Tests for castor.memory.replay — episode replay pipeline."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from castor.memory.replay import (
    ReplayStats,
    _get_indexed_ids,
    _load_episode,
    _parse_episode_timestamp,
    replay_episodes,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────


def make_episode(tmp_path: Path, ep_id: str, timestamp: str = "2026-01-15T10:00:00") -> Path:
    ep_dir = tmp_path / "L0-episodic" / "episodes"
    ep_dir.mkdir(parents=True, exist_ok=True)
    path = ep_dir / f"{ep_id}.json"
    path.write_text(
        json.dumps(
            {
                "episode_id": ep_id,
                "timestamp": timestamp,
                "observations": [{"type": "move", "value": 1.0}],
            }
        )
    )
    return path


def make_semantic_index(tmp_path: Path, indexed_ids: list[str]) -> None:
    sem_dir = tmp_path / "L1-semantic"
    sem_dir.mkdir(parents=True, exist_ok=True)
    for i, ep_id in enumerate(indexed_ids):
        (sem_dir / f"insight_{i}.json").write_text(
            json.dumps(
                {
                    "source_episode_ids": [ep_id],
                    "insight": f"insight from {ep_id}",
                }
            )
        )


# ── _load_episode ─────────────────────────────────────────────────────────────


def test_load_episode_valid(tmp_path):
    path = tmp_path / "ep.json"
    path.write_text('{"episode_id": "abc", "value": 42}')
    ep = _load_episode(path)
    assert ep is not None
    assert ep["episode_id"] == "abc"


def test_load_episode_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not json {{{")
    assert _load_episode(path) is None


def test_load_episode_missing(tmp_path):
    assert _load_episode(tmp_path / "nonexistent.json") is None


# ── _parse_episode_timestamp ─────────────────────────────────────────────────


def test_parse_timestamp_iso(tmp_path):
    path = tmp_path / "ep.json"
    path.write_text("{}")
    ep = {"timestamp": "2026-01-15T10:00:00"}
    ts = _parse_episode_timestamp(ep, path)
    assert ts is not None
    assert ts.year == 2026
    assert ts.month == 1


def test_parse_timestamp_unix(tmp_path):
    path = tmp_path / "ep.json"
    path.write_text("{}")
    ep = {"timestamp": 1737000000.0}
    ts = _parse_episode_timestamp(ep, path)
    assert ts is not None
    assert ts.year >= 2025


def test_parse_timestamp_fallback_mtime(tmp_path):
    path = tmp_path / "ep.json"
    path.write_text("{}")
    ep = {}  # no timestamp field
    ts = _parse_episode_timestamp(ep, path)
    assert ts is not None


# ── _get_indexed_ids ──────────────────────────────────────────────────────────


def test_get_indexed_ids_empty(tmp_path):
    sem_dir = tmp_path / "L1-semantic"
    sem_dir.mkdir()
    assert _get_indexed_ids(sem_dir) == set()


def test_get_indexed_ids_missing_dir(tmp_path):
    assert _get_indexed_ids(tmp_path / "nonexistent") == set()


def test_get_indexed_ids_from_source_episode_ids(tmp_path):
    make_semantic_index(tmp_path, ["ep001", "ep002"])
    ids = _get_indexed_ids(tmp_path / "L1-semantic")
    assert "ep001" in ids
    assert "ep002" in ids


# ── replay_episodes ─────────────────────────────────────────────────────────


def test_replay_dry_run_basic(tmp_path):
    make_episode(tmp_path, "ep001", "2026-01-15T10:00:00")
    make_episode(tmp_path, "ep002", "2026-01-20T10:00:00")

    stats = asyncio.run(
        replay_episodes(
            episodes_dir=tmp_path / "L0-episodic" / "episodes",
            semantic_dir=tmp_path / "L1-semantic",
            dry_run=True,
        )
    )

    assert stats.episodes_found == 2
    assert stats.episodes_replayed == 2
    assert stats.episodes_skipped == 0
    assert not stats.errors


def test_replay_skips_indexed_episodes(tmp_path):
    make_episode(tmp_path, "ep001", "2026-01-15T10:00:00")
    make_episode(tmp_path, "ep002", "2026-01-20T10:00:00")
    make_semantic_index(tmp_path, ["ep001"])  # ep001 already indexed

    stats = asyncio.run(
        replay_episodes(
            episodes_dir=tmp_path / "L0-episodic" / "episodes",
            semantic_dir=tmp_path / "L1-semantic",
            dry_run=True,
        )
    )

    assert stats.episodes_skipped == 1
    assert stats.episodes_replayed == 1


def test_replay_since_filter(tmp_path):
    make_episode(tmp_path, "old_ep", "2025-12-01T10:00:00")
    make_episode(tmp_path, "new_ep", "2026-02-01T10:00:00")

    stats = asyncio.run(
        replay_episodes(
            episodes_dir=tmp_path / "L0-episodic" / "episodes",
            semantic_dir=tmp_path / "L1-semantic",
            since="2026-01-01",
            dry_run=True,
        )
    )

    assert stats.episodes_replayed == 1  # only new_ep


def test_replay_episode_id_filter(tmp_path):
    make_episode(tmp_path, "ep001", "2026-01-15T10:00:00")
    make_episode(tmp_path, "ep002", "2026-01-20T10:00:00")

    stats = asyncio.run(
        replay_episodes(
            episodes_dir=tmp_path / "L0-episodic" / "episodes",
            semantic_dir=tmp_path / "L1-semantic",
            episode_id="ep001",
            dry_run=True,
        )
    )

    assert stats.episodes_replayed == 1


def test_replay_empty_dir(tmp_path):
    ep_dir = tmp_path / "L0-episodic" / "episodes"
    ep_dir.mkdir(parents=True)

    stats = asyncio.run(
        replay_episodes(
            episodes_dir=ep_dir,
            semantic_dir=tmp_path / "L1-semantic",
            dry_run=True,
        )
    )

    assert stats.episodes_found == 0
    assert stats.episodes_replayed == 0


def test_replay_missing_dir(tmp_path):
    stats = asyncio.run(
        replay_episodes(
            episodes_dir=tmp_path / "nonexistent" / "episodes",
            dry_run=True,
        )
    )
    # Should fail gracefully (no crash)
    assert isinstance(stats, ReplayStats)


def test_replay_invalid_since(tmp_path):
    ep_dir = tmp_path / "L0-episodic" / "episodes"
    ep_dir.mkdir(parents=True)

    stats = asyncio.run(
        replay_episodes(
            episodes_dir=ep_dir,
            since="not-a-date",
            dry_run=True,
        )
    )

    assert stats.errors


def test_replay_with_custom_consolidation_fn(tmp_path):
    make_episode(tmp_path, "ep001")

    call_count = {"n": 0}

    async def mock_consolidate(ep):
        call_count["n"] += 1
        return {"promoted": 2, "merged": 1}

    stats = asyncio.run(
        replay_episodes(
            episodes_dir=tmp_path / "L0-episodic" / "episodes",
            semantic_dir=tmp_path / "L1-semantic",
            consolidation_fn=mock_consolidate,
            dry_run=False,
        )
    )

    assert call_count["n"] == 1
    assert stats.insights_promoted == 2
    assert stats.insights_merged == 1


# ── ReplayStats ───────────────────────────────────────────────────────────────


def test_replay_stats_summary():
    stats = ReplayStats(
        episodes_found=10,
        episodes_skipped=3,
        episodes_replayed=7,
        insights_promoted=14,
        insights_merged=2,
        elapsed_s=1.5,
    )
    summary = stats.summary()
    assert "10" in summary
    assert "14" in summary
    assert "1.5s" in summary
