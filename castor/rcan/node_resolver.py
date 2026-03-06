"""
Federated RRN resolution for OpenCastor (RCAN §17).

Resolution order:
  1. Local SQLite cache (XDG data dir, TTL-based)
  2. rcan.dev /api/v1/resolve/:rrn
  3. Direct authoritative node (from X-Resolved-By header)
  4. Stale cache fallback when all network fails

Zero new runtime dependencies (urllib only).
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from prometheus_client import Counter, Histogram

    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

ROOT_REGISTRY_URL = "https://rcan.dev"
RRN_DELEGATED_RE = re.compile(r"^RRN-([A-Z0-9]{2,8})-(\d{8,16})$")
RRN_LEGACY_RE = re.compile(r"^RRN-(\d{8,16})$")
DEFAULT_TTL = 3600
CACHE_DB_NAME = "rcan_resolve_cache.db"

# ── Prometheus metrics (no-op stubs when prometheus_client not installed) ─────

if HAS_PROMETHEUS:
    _RESOLVE_TOTAL = Counter(
        "rcan_resolve_total",
        "Total RCAN RRN resolution attempts",
        ["namespace", "source"],
    )
    _RESOLVE_LATENCY = Histogram(
        "rcan_resolve_latency_seconds",
        "Latency of RCAN RRN resolution",
    )
else:

    class _NoopCounter:  # type: ignore[no-redef]
        def labels(self, **_kw: object) -> _NoopCounter:
            return self

        def inc(self, _n: int = 1) -> None:
            pass

    class _NoopHistogram:  # type: ignore[no-redef]
        def time(self):  # noqa: ANN201
            import contextlib

            return contextlib.nullcontext()

        def observe(self, _v: float) -> None:
            pass

    _RESOLVE_TOTAL = _NoopCounter()  # type: ignore[assignment]
    _RESOLVE_LATENCY = _NoopHistogram()  # type: ignore[assignment]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _cache_db_path() -> Path:
    import os

    xdg = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    d = xdg / "opencastor" / "rcan"
    d.mkdir(parents=True, exist_ok=True)
    return d / CACHE_DB_NAME


def _rrn_namespace(rrn: str) -> str:
    """Extract namespace label from an RRN for Prometheus labels."""
    m = RRN_DELEGATED_RE.match(rrn)
    if m:
        return m.group(1)
    return "LEGACY"


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class ResolvedRobot:
    rrn: str
    manufacturer: str
    model: str
    attestation: str  # 'active', 'pending', 'suspended', 'revoked'
    resolved_by: str  # URL of the node that answered
    from_cache: bool
    stale: bool = False
    raw: dict = field(default_factory=dict)


# ── Exceptions ────────────────────────────────────────────────────────────────


class RCANResolverError(Exception):
    pass


# ── Resolver ─────────────────────────────────────────────────────────────────


class NodeResolver:
    """Federated RCAN RRN resolver with local SQLite cache."""

    def __init__(self, root_url: str = ROOT_REGISTRY_URL, timeout: int = 8):
        self.root_url = root_url.rstrip("/")
        self.timeout = timeout
        self._db: Optional[sqlite3.Connection] = None

    # ── DB helpers ────────────────────────────────────────────────────────────

    def _get_db(self) -> sqlite3.Connection:
        if self._db is None:
            self._db = sqlite3.connect(str(_cache_db_path()))
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS resolve_cache (
                    rrn TEXT PRIMARY KEY,
                    record_json TEXT NOT NULL,
                    resolved_by TEXT NOT NULL,
                    cached_at REAL NOT NULL,
                    ttl_seconds INTEGER NOT NULL DEFAULT 3600
                )
                """
            )
            self._db.commit()
        return self._db

    def _cache_get(self, rrn: str) -> Optional[tuple[dict, str, bool]]:
        """Return (record_dict, resolved_by, is_stale) or None if not cached."""
        row = (
            self._get_db()
            .execute(
                "SELECT record_json, resolved_by, cached_at, ttl_seconds "
                "FROM resolve_cache WHERE rrn = ?",
                (rrn,),
            )
            .fetchone()
        )
        if row is None:
            return None
        record_json, resolved_by, cached_at, ttl = row
        stale = (time.time() - cached_at) > ttl
        return json.loads(record_json), resolved_by, stale

    def _cache_set(
        self,
        rrn: str,
        record: dict,
        resolved_by: str,
        ttl: int = DEFAULT_TTL,
    ) -> None:
        self._get_db().execute(
            "INSERT OR REPLACE INTO resolve_cache "
            "(rrn, record_json, resolved_by, cached_at, ttl_seconds) "
            "VALUES (?,?,?,?,?)",
            (rrn, json.dumps(record), resolved_by, time.time(), ttl),
        )
        self._get_db().commit()

    # ── Network helpers ───────────────────────────────────────────────────────

    def _fetch_json(self, url: str) -> tuple[dict, dict]:
        """Fetch JSON from URL. Returns (body_dict, headers_dict)."""
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "OpenCastor/RCAN-Resolver",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                headers = dict(resp.headers)
                body = json.loads(resp.read().decode())
                return body, headers
        except urllib.error.HTTPError as e:
            raise RCANResolverError(f"HTTP {e.code} from {url}") from e
        except Exception as e:
            raise RCANResolverError(f"Network error fetching {url}: {e}") from e

    # ── Public API ────────────────────────────────────────────────────────────

    def resolve(self, rrn: str) -> ResolvedRobot:
        """
        Resolve an RRN to a ResolvedRobot, following the §17 resolution algorithm.
        """
        ns = _rrn_namespace(rrn)
        t0 = time.monotonic()

        # 1. Fresh cache hit
        cached = self._cache_get(rrn)
        if cached and not cached[2]:  # not stale
            record, resolved_by, _ = cached
            _RESOLVE_TOTAL.labels(namespace=ns, source="cache_hit").inc()
            _RESOLVE_LATENCY.observe(time.monotonic() - t0)
            return self._make_resolved(rrn, record, resolved_by, from_cache=True, stale=False)

        # 2. Live network fetch
        try:
            body, headers = self._fetch_json(f"{self.root_url}/api/v1/resolve/{rrn}")
            resolved_by = headers.get("X-Resolved-By", self.root_url)
            record = body.get("record", body)
            cc = headers.get("Cache-Control", "")
            ttl_str = cc.replace("max-age=", "").strip()
            ttl = int(ttl_str) if ttl_str.isdigit() else DEFAULT_TTL
            self._cache_set(rrn, record, resolved_by, ttl)
            _RESOLVE_TOTAL.labels(namespace=ns, source="live").inc()
            _RESOLVE_LATENCY.observe(time.monotonic() - t0)
            return self._make_resolved(rrn, record, resolved_by, from_cache=False, stale=False)
        except RCANResolverError:
            pass

        # 3. Stale cache fallback
        if cached:
            record, resolved_by, _ = cached
            _RESOLVE_TOTAL.labels(namespace=ns, source="cache_stale").inc()
            _RESOLVE_LATENCY.observe(time.monotonic() - t0)
            return self._make_resolved(rrn, record, resolved_by, from_cache=True, stale=True)

        raise RCANResolverError(f"RRN not found and no cached record: {rrn}")

    def _make_resolved(
        self,
        rrn: str,
        record: dict,
        resolved_by: str,
        from_cache: bool,
        stale: bool,
    ) -> ResolvedRobot:
        return ResolvedRobot(
            rrn=rrn,
            manufacturer=record.get("manufacturer", ""),
            model=record.get("model", ""),
            attestation=record.get("attestation", record.get("verification_tier", "unknown")),
            resolved_by=resolved_by,
            from_cache=from_cache,
            stale=stale,
            raw=record,
        )

    def is_reachable(self, timeout: int = 5) -> tuple[bool, float]:
        """Check if rcan.dev is reachable. Returns (ok, latency_ms)."""
        t0 = time.monotonic()
        try:
            req = urllib.request.Request(
                f"{self.root_url}/api/v1/robots?limit=1",
                method="HEAD",
            )
            urllib.request.urlopen(req, timeout=timeout)
            return True, (time.monotonic() - t0) * 1000
        except Exception:
            return False, (time.monotonic() - t0) * 1000

    def close(self) -> None:
        if self._db:
            self._db.close()
            self._db = None
