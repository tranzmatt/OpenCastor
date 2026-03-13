"""Tests for castor.orchestration.thread_context — ThreadContextBus (#613)."""

from __future__ import annotations

import threading

import pytest

from castor.orchestration.thread_context import ThreadContextBus, ThreadUpdate


@pytest.fixture()
def bus():
    return ThreadContextBus()


def _make_update(thread_id: str = "t1", status: str = "running", summary: str = "doing work"):
    return ThreadUpdate(thread_id=thread_id, skill="move", status=status, summary=summary)


def test_publish_and_get(bus):
    bus.publish(_make_update("t1", "running", "step 1"))
    bus.publish(_make_update("t1", "complete", "step 2"))
    updates = bus.get_updates("t1")
    assert len(updates) == 2
    assert updates[0].status == "running"
    assert updates[1].status == "complete"


def test_get_summary_format(bus):
    bus.publish(_make_update("alpha", "blocked", "waiting for sensor"))
    summary = bus.get_summary("alpha")
    assert "alpha" in summary
    assert "blocked" in summary
    assert "Updates: 1" in summary


def test_get_summary_no_updates(bus):
    summary = bus.get_summary("ghost")
    assert "ghost" in summary
    assert "No updates yet" in summary


def test_get_all_summaries(bus):
    bus.publish(_make_update("t1", "running", "a"))
    bus.publish(_make_update("t2", "complete", "b"))
    summaries = bus.get_all_summaries()
    assert "t1" in summaries
    assert "t2" in summaries
    assert "running" in summaries["t1"]
    assert "complete" in summaries["t2"]


def test_clear(bus):
    bus.publish(_make_update("t1"))
    bus.clear("t1")
    assert bus.get_updates("t1") == []
    summaries = bus.get_all_summaries()
    assert "t1" not in summaries


def test_thread_safe(bus):
    errors = []

    def worker(i):
        try:
            bus.publish(_make_update(f"thread-{i}", "running", f"worker {i}"))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(bus.get_all_summaries()) == 10
