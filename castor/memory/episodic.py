"""Episodic memory — stores successful skill executions for future recall."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".opencastor" / "episodic.db"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    episode_id TEXT PRIMARY KEY,
    task TEXT NOT NULL,
    outcome TEXT NOT NULL,
    context_summary TEXT,
    duration_ms INTEGER,
    timestamp REAL,
    tags TEXT
);
CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id TEXT NOT NULL,
    role TEXT,
    content TEXT,
    FOREIGN KEY (episode_id) REFERENCES episodes(episode_id)
);
CREATE INDEX IF NOT EXISTS idx_episodes_task ON episodes(task);
"""


@dataclass
class Episode:
    episode_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task: str = ""
    outcome: str = "success"
    critical_tool_calls: list[dict] = field(default_factory=list)
    context_summary: str = ""
    duration_ms: int = 0
    timestamp: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)


class EpisodicMemory:
    """SQLite-backed episodic memory store."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        raw = str(db_path) if db_path is not None else str(_DEFAULT_DB)
        self._in_memory = raw == ":memory:"
        if self._in_memory:
            self._db = ":memory:"
            self._shared_conn: sqlite3.Connection | None = sqlite3.connect(":memory:")
        else:
            self._db = raw
            self._shared_conn = None
            Path(self._db).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = self._conn()
        conn.executescript(_SCHEMA)
        if not self._in_memory:
            conn.close()

    def _conn(self) -> sqlite3.Connection:
        if self._in_memory:
            return self._shared_conn  # type: ignore[return-value]
        return sqlite3.connect(self._db)

    def record(
        self,
        task: str,
        session_log: list[dict],
        outcome: str = "success",
        duration_ms: int = 0,
        tags: list[str] | None = None,
    ) -> Episode:
        """Prune session log to critical path and persist."""
        critical = self._prune_to_critical(session_log, outcome)
        summary = self._summarize(critical)
        ep = Episode(
            task=task,
            outcome=outcome,
            critical_tool_calls=critical,
            context_summary=summary,
            duration_ms=duration_ms,
            tags=tags or [],
        )
        self._save(ep)
        logger.info("Recorded episode %s for task %r (outcome=%s)", ep.episode_id, task, outcome)
        return ep

    def recall(self, task: str, top_k: int = 3) -> list[Episode]:
        """Retrieve most recent successful episodes for a task."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT episode_id, task, outcome, context_summary, duration_ms, timestamp, tags "
                "FROM episodes WHERE outcome='success' AND task LIKE ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (f"%{task}%", top_k),
            ).fetchall()
        finally:
            if not self._in_memory:
                conn.close()
        return [self._row_to_episode(r) for r in rows]

    def inject_context(self, task: str, top_k: int = 2) -> str:
        """Return a prompt prefix with relevant past episodes."""
        episodes = self.recall(task, top_k)
        if not episodes:
            return ""
        lines = ["[Episodic memory — relevant past sessions:]"]
        for ep in episodes:
            lines.append(f"- Task: {ep.task} | Outcome: {ep.outcome} | {ep.context_summary}")
        return "\n".join(lines)

    def _prune_to_critical(self, log: list[dict], outcome: str) -> list[dict]:
        """Keep only non-empty assistant/tool messages. Heuristic critical-path filter."""
        if outcome != "success":
            return log[-5:] if len(log) > 5 else log
        return [m for m in log if m.get("role") in ("assistant", "tool") and m.get("content")]

    def _summarize(self, tool_calls: list[dict]) -> str:
        if not tool_calls:
            return "No tool calls recorded."
        return f"{len(tool_calls)} actions recorded."

    def _save(self, ep: Episode) -> None:
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO episodes VALUES (?,?,?,?,?,?,?)",
                (
                    ep.episode_id,
                    ep.task,
                    ep.outcome,
                    ep.context_summary,
                    ep.duration_ms,
                    ep.timestamp,
                    json.dumps(ep.tags),
                ),
            )
            for tc in ep.critical_tool_calls:
                conn.execute(
                    "INSERT INTO tool_calls (episode_id, role, content) VALUES (?,?,?)",
                    (ep.episode_id, tc.get("role"), str(tc.get("content", ""))),
                )
            conn.commit()
        finally:
            if not self._in_memory:
                conn.close()

    def _row_to_episode(self, row: tuple) -> Episode:
        eid, task, outcome, summary, dur, ts, tags_json = row
        return Episode(
            episode_id=eid,
            task=task,
            outcome=outcome,
            context_summary=summary,
            duration_ms=dur or 0,
            timestamp=ts or 0,
            tags=json.loads(tags_json or "[]"),
        )
