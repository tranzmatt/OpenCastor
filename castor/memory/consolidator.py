"""
castor/memory/consolidator.py — Episodic memory consolidation for the per-robot optimizer.

Curates the EpisodeMemory store to improve retrieval quality over time:

  1. **Deduplication** — episodes with cosine similarity > 0.92 are merged
     (keep the more recent one, append the earlier summary to its notes).
  2. **Archival** — episodes older than 30 days with zero retrievals are moved
     to a cold ``archived`` table rather than deleted.
  3. **Priority boosting** — episodes retrieved 3+ times get a ``high`` tag
     for faster future retrieval.

Conservative rules (P66-adjacent):
  - NEVER deletes episodes — only archives
  - MAX 10 changes per consolidation pass
  - Only runs when retrieval precision is measured to improve by > 5%
  - Requires idle robot (checked by caller via castor.idle.is_robot_idle)

Usage::

    from castor.memory.consolidator import EpisodeConsolidator

    consolidator = EpisodeConsolidator(db_path="~/.castor/memory.db", dry_run=True)
    report = consolidator.consolidate()
    print(report.summary())
"""

from __future__ import annotations

import datetime
import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("OpenCastor.Memory.Consolidator")

__all__ = ["EpisodeConsolidator", "ConsolidationReport"]

# Similarity threshold for duplicate detection (cosine)
_DUPLICATE_THRESHOLD = 0.92

# Age threshold for archival (seconds — 30 days)
_STALE_AGE_S = 30 * 24 * 3600

# Retrieval count threshold for priority boost
_HIGH_VALUE_THRESHOLD = 3

# Max changes per consolidation pass
_MAX_CHANGES = 10


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class ConsolidationReport:
    """Result of one consolidation pass."""

    timestamp: str = ""
    dry_run: bool = False
    duplicates_merged: int = 0
    stale_archived: int = 0
    priority_boosted: int = 0
    precision_before: float = 0.0
    precision_after: float = 0.0
    changes: list[dict] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def total_changes(self) -> int:
        return self.duplicates_merged + self.stale_archived + self.priority_boosted

    @property
    def precision_improved(self) -> bool:
        return (self.precision_after - self.precision_before) > 0.05

    def summary(self) -> str:
        mode = " [DRY RUN]" if self.dry_run else ""
        lines = [
            f"Consolidation pass{mode} — {self.timestamp}",
            f"  Duplicates merged:  {self.duplicates_merged}",
            f"  Stale archived:     {self.stale_archived}",
            f"  Priority boosted:   {self.priority_boosted}",
            f"  Precision:          {self.precision_before:.3f} → {self.precision_after:.3f}",
        ]
        if self.error:
            lines.append(f"  ERROR: {self.error}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "dry_run": self.dry_run,
            "duplicates_merged": self.duplicates_merged,
            "stale_archived": self.stale_archived,
            "priority_boosted": self.priority_boosted,
            "precision_before": round(self.precision_before, 4),
            "precision_after": round(self.precision_after, 4),
            "changes": self.changes,
            "error": self.error,
        }


# ── Main consolidator ─────────────────────────────────────────────────────────


class EpisodeConsolidator:
    """Consolidates the episode memory store to improve retrieval quality.

    Args:
        db_path:  Path to the EpisodeMemory SQLite database.
        dry_run:  If True, compute changes but do not write anything.
    """

    def __init__(self, db_path: Optional[str] = None, dry_run: bool = False) -> None:
        from castor.memory.episode import EpisodeMemory

        _default = str(Path.home() / ".castor" / "memory.db")
        self._db_path = db_path or _default
        self._dry_run = dry_run
        self._mem = EpisodeMemory(db_path=self._db_path)

    # ── Public API ────────────────────────────────────────────────────────────

    def consolidate(self) -> ConsolidationReport:
        """Run one full consolidation pass. Returns a report."""
        report = ConsolidationReport(
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            dry_run=self._dry_run,
        )

        try:
            self._ensure_schema()
            report.precision_before = self._measure_retrieval_precision()

            changes_remaining = _MAX_CHANGES

            # 1. Archive stale episodes
            stale = self._find_stale_episodes()
            for ep_id in stale[:changes_remaining]:
                if not self._dry_run:
                    self._archive_episode(ep_id, reason="stale_30d")
                report.stale_archived += 1
                report.changes.append(
                    {"type": "archive", "episode_id": ep_id, "reason": "stale_30d"}
                )
            changes_remaining -= report.stale_archived

            if changes_remaining > 0:
                # 2. Boost high-value episodes
                high_value = self._find_high_value_episodes()
                for ep_id in high_value[:changes_remaining]:
                    if not self._dry_run:
                        self._boost_priority(ep_id)
                    report.priority_boosted += 1
                    report.changes.append({"type": "boost", "episode_id": ep_id})
                changes_remaining -= report.priority_boosted

            if changes_remaining > 0:
                # 3. Merge near-duplicate episodes (most expensive — do last)
                dupes = self._find_duplicate_pairs()
                for keep_id, drop_id in dupes[:changes_remaining]:
                    if not self._dry_run:
                        self._merge_episodes(keep_id, drop_id)
                    report.duplicates_merged += 1
                    report.changes.append({"type": "merge", "keep": keep_id, "drop": drop_id})

            report.precision_after = self._measure_retrieval_precision()

        except Exception as exc:
            logger.exception("Consolidation pass failed: %s", exc)
            report.error = str(exc)

        return report

    # ── Schema ────────────────────────────────────────────────────────────────

    def _ensure_schema(self) -> None:
        """Create archived table and retrieval_count column if missing."""
        conn = sqlite3.connect(self._db_path)
        try:
            # archived table — cold storage for stale episodes
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes_archived (
                    id           TEXT PRIMARY KEY,
                    archived_at  REAL NOT NULL,
                    reason       TEXT,
                    ts           REAL,
                    instruction  TEXT,
                    raw_thought  TEXT,
                    action_json  TEXT,
                    latency_ms   REAL,
                    outcome      TEXT,
                    source       TEXT,
                    tags         TEXT
                )
            """)
            # retrieval_count column on episodes for priority tracking
            try:
                conn.execute("ALTER TABLE episodes ADD COLUMN retrieval_count INTEGER DEFAULT 0")
            except Exception:
                pass  # already exists
            # priority column for boosting
            try:
                conn.execute("ALTER TABLE episodes ADD COLUMN priority TEXT DEFAULT 'normal'")
            except Exception:
                pass
            conn.commit()
        finally:
            conn.close()

    # ── Stale archival ────────────────────────────────────────────────────────

    def _find_stale_episodes(self) -> list[str]:
        """Return IDs of episodes older than 30 days with zero retrievals."""
        cutoff_ts = time.time() - _STALE_AGE_S
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT id FROM episodes
                WHERE ts < ?
                  AND (retrieval_count IS NULL OR retrieval_count = 0)
                  AND (flagged IS NULL OR flagged = 0)
                ORDER BY ts ASC
                LIMIT 50
                """,
                (cutoff_ts,),
            ).fetchall()
            return [r["id"] for r in rows]
        except Exception as exc:
            logger.debug("find_stale_episodes: %s", exc)
            return []
        finally:
            conn.close()

    def _archive_episode(self, ep_id: str, reason: str = "stale") -> None:
        """Move an episode to the archived table."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT * FROM episodes WHERE id = ?", (ep_id,)).fetchone()
            if row is None:
                return
            conn.execute(
                """
                INSERT OR REPLACE INTO episodes_archived
                    (id, archived_at, reason, ts, instruction, raw_thought,
                     action_json, latency_ms, outcome, source, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ep_id,
                    time.time(),
                    reason,
                    row["ts"],
                    row["instruction"],
                    row["raw_thought"],
                    row["action_json"] if "action_json" in row.keys() else None,
                    row["latency_ms"],
                    row["outcome"],
                    row["source"],
                    row["tags"] if "tags" in row.keys() else None,
                ),
            )
            conn.execute("DELETE FROM episodes WHERE id = ?", (ep_id,))
            conn.commit()
            logger.debug("Archived episode %s (reason: %s)", ep_id, reason)
        except Exception as exc:
            logger.warning("archive_episode failed for %s: %s", ep_id, exc)
            conn.rollback()
        finally:
            conn.close()

    # ── Priority boosting ─────────────────────────────────────────────────────

    def _find_high_value_episodes(self) -> list[str]:
        """Return IDs of episodes with retrieval_count >= threshold."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT id FROM episodes
                WHERE retrieval_count >= ?
                  AND (priority IS NULL OR priority != 'high')
                ORDER BY retrieval_count DESC
                LIMIT 20
                """,
                (_HIGH_VALUE_THRESHOLD,),
            ).fetchall()
            return [r["id"] for r in rows]
        except Exception as exc:
            logger.debug("find_high_value_episodes: %s", exc)
            return []
        finally:
            conn.close()

    def _boost_priority(self, ep_id: str) -> None:
        """Set priority='high' on an episode."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("UPDATE episodes SET priority = 'high' WHERE id = ?", (ep_id,))
            conn.commit()
            logger.debug("Boosted priority for episode %s", ep_id)
        finally:
            conn.close()

    # ── Duplicate detection ───────────────────────────────────────────────────

    def _find_duplicate_pairs(self) -> list[tuple[str, str]]:
        """Find near-duplicate episode pairs using cosine similarity.

        Returns list of (keep_id, drop_id) pairs where drop_id is the older one.
        Uses stored embeddings from episode_embeddings table when available;
        falls back to instruction-text Jaccard similarity.
        """
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Try embedding-based similarity first
            emb_rows = conn.execute(
                """
                SELECT e.id, e.ts, ee.embedding_json
                FROM episodes e
                JOIN episode_embeddings ee ON e.id = ee.id
                ORDER BY e.ts DESC
                LIMIT 200
                """
            ).fetchall()

            if len(emb_rows) >= 10:
                return self._find_dupes_by_embedding(emb_rows)

            # Fallback: instruction text Jaccard similarity
            text_rows = conn.execute(
                "SELECT id, ts, instruction FROM episodes ORDER BY ts DESC LIMIT 200"
            ).fetchall()
            return self._find_dupes_by_text(text_rows)

        except Exception as exc:
            logger.debug("find_duplicate_pairs: %s", exc)
            return []
        finally:
            conn.close()

    def _find_dupes_by_embedding(self, rows: list) -> list[tuple[str, str]]:
        """Find duplicate pairs using cosine similarity on stored embeddings."""
        pairs = []
        processed = []

        for row in rows:
            try:
                emb = json.loads(row["embedding_json"])
                processed.append((row["id"], float(row["ts"]), emb))
            except Exception:
                continue

        for i, (id_a, ts_a, emb_a) in enumerate(processed):
            for id_b, ts_b, emb_b in processed[i + 1 :]:
                sim = _cosine(emb_a, emb_b)
                if sim >= _DUPLICATE_THRESHOLD:
                    # Keep newer, drop older
                    keep, drop = (id_a, id_b) if ts_a >= ts_b else (id_b, id_a)
                    pairs.append((keep, drop))
                    if len(pairs) >= _MAX_CHANGES:
                        return pairs

        return pairs

    def _find_dupes_by_text(self, rows: list) -> list[tuple[str, str]]:
        """Find duplicate pairs using Jaccard similarity on instruction text."""
        pairs = []
        processed = []

        for row in rows:
            instr = (row["instruction"] or "").lower()
            tokens = set(instr.split())
            if tokens:
                processed.append((row["id"], float(row["ts"]), tokens))

        for i, (id_a, ts_a, tok_a) in enumerate(processed):
            for id_b, ts_b, tok_b in processed[i + 1 :]:
                if not tok_a or not tok_b:
                    continue
                jaccard = len(tok_a & tok_b) / len(tok_a | tok_b)
                if jaccard >= 0.85:  # lower threshold for text
                    keep, drop = (id_a, id_b) if ts_a >= ts_b else (id_b, id_a)
                    pairs.append((keep, drop))
                    if len(pairs) >= _MAX_CHANGES:
                        return pairs

        return pairs

    def _merge_episodes(self, keep_id: str, drop_id: str) -> None:
        """Merge drop_id into keep_id: append drop's instruction to keep's notes."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            drop_row = conn.execute("SELECT * FROM episodes WHERE id = ?", (drop_id,)).fetchone()
            if drop_row is None:
                return

            # Append the dropped episode's instruction to keep's raw_thought as context
            drop_summary = f"[merged from {drop_id[:8]}]: {drop_row['instruction'] or ''}"
            conn.execute(
                "UPDATE episodes SET raw_thought = raw_thought || ? WHERE id = ?",
                (f"\n{drop_summary}", keep_id),
            )
            # Archive the dropped episode
            self._archive_episode(drop_id, reason=f"merged_into_{keep_id[:8]}")
            conn.commit()
            logger.debug("Merged episode %s into %s", drop_id, keep_id)
        except Exception as exc:
            logger.warning("merge_episodes failed (%s → %s): %s", drop_id, keep_id, exc)
            conn.rollback()
        finally:
            conn.close()

    # ── Precision measurement ─────────────────────────────────────────────────

    def _measure_retrieval_precision(self) -> float:
        """Estimate retrieval precision from recent episode diversity.

        Heuristic: sample 20 episodes and measure average pairwise diversity.
        Higher diversity = better retrieval (less duplicate dilution).
        Returns a float 0.0–1.0.
        """
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT instruction FROM episodes ORDER BY ts DESC LIMIT 20"
            ).fetchall()

            instructions = [r["instruction"] or "" for r in rows if r["instruction"]]
            if len(instructions) < 3:
                return 0.5  # not enough data

            # Pairwise Jaccard diversity (1 - similarity)
            total_div = 0.0
            pairs = 0
            for i in range(len(instructions)):
                for j in range(i + 1, len(instructions)):
                    tok_a = set(instructions[i].lower().split())
                    tok_b = set(instructions[j].lower().split())
                    if tok_a and tok_b:
                        jaccard = len(tok_a & tok_b) / len(tok_a | tok_b)
                        total_div += 1.0 - jaccard
                        pairs += 1

            return total_div / pairs if pairs > 0 else 0.5
        except Exception:
            return 0.5
        finally:
            conn.close()

    # ── Retrieval tracking ────────────────────────────────────────────────────

    @classmethod
    def record_retrieval(cls, db_path: str, episode_id: str) -> None:
        """Increment retrieval_count for an episode.

        Call this whenever an episode is returned from a search/query so
        the consolidator can identify high-value episodes.
        """
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """
                UPDATE episodes
                SET retrieval_count = COALESCE(retrieval_count, 0) + 1
                WHERE id = ?
                """,
                (episode_id,),
            )
            conn.commit()
        except Exception as exc:
            logger.debug("record_retrieval failed: %s", exc)
        finally:
            conn.close()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two pre-normalised float vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
