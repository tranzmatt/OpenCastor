"""castor.incidents — post-market monitoring incident log (EU AI Act Art. 72).

Provides a persistent JSONL-based incident log and Art. 72-structured report generator.

Usage:
    from castor.incidents import IncidentLog, IncidentSeverity, generate_report

    log = IncidentLog()  # default: ~/.opencastor/incidents.jsonl
    log.record(IncidentSeverity.LIFE_HEALTH, "estop_failure", "ESTOP triggered", state)
    report = generate_report(log)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

INCIDENT_SCHEMA_VERSION = "rcan-incidents-v1"
DEFAULT_INCIDENT_LOG_PATH = Path.home() / ".opencastor" / "incidents.jsonl"

# EU AI Act Art. 72 reporting deadlines:
# - life_health: 15 days from discovery
# - other: 3 months from discovery
REPORTING_DEADLINES_DAYS = {
    "life_health": 15,
    "other": 90,
}


class IncidentSeverity(str, Enum):
    LIFE_HEALTH = "life_health"  # Risk to life or health — 15-day reporting deadline
    OTHER = "other"  # All other serious incidents — 3-month deadline


class IncidentLog:
    """Persistent JSONL incident log for Art. 72 post-market monitoring.

    Each incident is stored as a JSON line in a JSONL file.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path else DEFAULT_INCIDENT_LOG_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        severity: IncidentSeverity,
        category: str,
        description: str,
        system_state: dict[str, Any],
    ) -> str:
        """Record a new incident. Returns the incident ID (UUID4)."""
        incident_id = str(uuid.uuid4())
        entry = {
            "id": incident_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": severity.value if isinstance(severity, IncidentSeverity) else str(severity),
            "category": category,
            "description": description,
            "system_state": system_state,
            "reported": False,
            "reporting_deadline_days": REPORTING_DEADLINES_DAYS.get(
                severity.value if isinstance(severity, IncidentSeverity) else str(severity),
                REPORTING_DEADLINES_DAYS["other"],
            ),
        }
        with open(self._path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        return incident_id

    def list_incidents(self) -> list[dict[str, Any]]:
        """Return all incidents from the log, oldest first."""
        if not self._path.exists():
            return []
        incidents = []
        with open(self._path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        incidents.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return incidents


def generate_report(log: IncidentLog) -> dict[str, Any]:
    """Generate an Art. 72-structured post-market monitoring report."""
    incidents = log.list_incidents()
    by_severity: dict[str, int] = {}
    for inc in incidents:
        sev = inc.get("severity", "other")
        by_severity[sev] = by_severity.get(sev, 0) + 1

    return {
        "schema": INCIDENT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_incidents": len(incidents),
        "incidents_by_severity": by_severity,
        "reporting_deadlines": REPORTING_DEADLINES_DAYS,
        "art72_note": (
            "EU AI Act Art. 72 requires providers of high-risk AI systems to report "
            "serious incidents to market surveillance authorities. "
            "life_health incidents: within 15 days. Other incidents: within 3 months."
        ),
        "incidents": incidents,
    }
