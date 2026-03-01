"""Tests for episode tagging (issue #270) — castor/memory.py."""

from __future__ import annotations

import pytest


@pytest.fixture()
def mem(tmp_path):
    from castor.memory import EpisodeMemory

    return EpisodeMemory(db_path=str(tmp_path / "tags.db"))


# ── log_episode with tags ─────────────────────────────────────────────────────


def test_log_episode_with_tags_stores_them(mem):
    mem.log_episode(instruction="patrol", action={}, tags=["patrol", "outdoor"])
    rows = mem.query_recent(limit=1)
    assert rows[0]["tags"] == ["patrol", "outdoor"]


def test_log_episode_without_tags_returns_empty_list(mem):
    mem.log_episode(instruction="stop", action={})
    rows = mem.query_recent(limit=1)
    assert rows[0]["tags"] == []


def test_log_episode_single_tag(mem):
    mem.log_episode(instruction="dock", action={}, tags=["indoor"])
    rows = mem.query_recent(limit=1)
    assert rows[0]["tags"] == ["indoor"]


# ── add_tags ──────────────────────────────────────────────────────────────────


def test_add_tags_to_existing_episode(mem):
    ep_id = mem.log_episode(instruction="navigate", action={}, tags=["outdoor"])
    ok = mem.add_tags(ep_id, ["night", "autonomous"])
    assert ok is True
    ep = mem.get_episode(ep_id)
    assert "outdoor" in ep["tags"]
    assert "night" in ep["tags"]
    assert "autonomous" in ep["tags"]


def test_add_tags_deduplicates(mem):
    ep_id = mem.log_episode(instruction="repeat", action={}, tags=["patrol"])
    mem.add_tags(ep_id, ["patrol", "outdoor"])
    ep = mem.get_episode(ep_id)
    assert ep["tags"].count("patrol") == 1


def test_add_tags_nonexistent_episode_returns_false(mem):
    ok = mem.add_tags("nonexistent-id-0000", ["tag"])
    assert ok is False


def test_add_tags_empty_list_returns_false(mem):
    ep_id = mem.log_episode(instruction="x", action={})
    ok = mem.add_tags(ep_id, [])
    assert ok is False


# ── query_recent with tag filtering ───────────────────────────────────────────


def test_query_recent_filters_by_single_tag(mem):
    mem.log_episode(instruction="patrol", action={}, tags=["patrol", "outdoor"])
    mem.log_episode(instruction="stop", action={}, tags=["indoor"])
    rows = mem.query_recent(limit=10, tags=["patrol"])
    assert len(rows) == 1
    assert "patrol" in rows[0]["tags"]


def test_query_recent_filters_require_all_tags(mem):
    mem.log_episode(instruction="a", action={}, tags=["patrol", "outdoor"])
    mem.log_episode(instruction="b", action={}, tags=["patrol", "indoor"])
    mem.log_episode(instruction="c", action={}, tags=["outdoor"])
    rows = mem.query_recent(limit=10, tags=["patrol", "outdoor"])
    assert len(rows) == 1
    assert rows[0]["instruction"] == "a"


def test_query_recent_no_filter_returns_all(mem):
    mem.log_episode(instruction="x", action={}, tags=["a"])
    mem.log_episode(instruction="y", action={})
    rows = mem.query_recent(limit=10)
    assert len(rows) == 2


def test_query_recent_tag_case_insensitive(mem):
    mem.log_episode(instruction="z", action={}, tags=["Patrol"])
    rows = mem.query_recent(limit=10, tags=["patrol"])
    assert len(rows) == 1


# ── API endpoints ─────────────────────────────────────────────────────────────


def test_api_memory_add_tags(tmp_path):
    """POST /api/memory/episodes/{id}/tags returns ok:True."""
    from fastapi.testclient import TestClient

    from castor.api import app, state
    from castor.memory import EpisodeMemory

    mem = EpisodeMemory(db_path=str(tmp_path / "api_tags.db"))
    ep_id = mem.log_episode(instruction="api test", action={})
    state.memory = mem

    client = TestClient(app)
    resp = client.post(
        f"/api/memory/episodes/{ep_id}/tags",
        json={"tags": ["test", "api"]},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    state.memory = None


def test_api_memory_add_tags_empty_returns_422(tmp_path):
    """POST /api/memory/episodes/{id}/tags with empty tags returns 422."""
    from fastapi.testclient import TestClient

    from castor.api import app

    client = TestClient(app)
    resp = client.post(
        "/api/memory/episodes/fake-id/tags",
        json={"tags": []},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 422
