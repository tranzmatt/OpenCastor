"""Shared-context thread bus for hive-mind orchestration."""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ThreadUpdate:
    thread_id: str
    skill: str
    status: str  # running | blocked | complete | error
    summary: str
    tool_calls: list = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class ThreadContextBus:
    """In-process pub/sub for live subagent state sharing."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._updates: dict[str, list[ThreadUpdate]] = defaultdict(list)

    def publish(self, update: ThreadUpdate) -> None:
        with self._lock:
            self._updates[update.thread_id].append(update)
        logger.debug(
            "ThreadBus: %s → %s (%s)", update.thread_id, update.status, update.summary[:60]
        )

    def get_updates(self, thread_id: str) -> list[ThreadUpdate]:
        with self._lock:
            return list(self._updates.get(thread_id, []))

    def get_summary(self, thread_id: str) -> str:
        """Return compressed summary of thread state for orchestrator."""
        updates = self.get_updates(thread_id)
        if not updates:
            return f"[{thread_id}] No updates yet."
        latest = updates[-1]
        return (
            f"[{thread_id}] Status: {latest.status} | "
            f"Last: {latest.summary} | Updates: {len(updates)}"
        )

    def get_all_summaries(self) -> dict[str, str]:
        with self._lock:
            thread_ids = list(self._updates.keys())
        return {tid: self.get_summary(tid) for tid in thread_ids}

    def clear(self, thread_id: str) -> None:
        with self._lock:
            self._updates.pop(thread_id, None)
