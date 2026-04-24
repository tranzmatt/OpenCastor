"""LoA (Level of Assurance) enforcement — reads ROBOT.md safety block.

Canonical source of truth: ``ROBOT.md`` frontmatter, ``safety:`` block. A
running gateway can be hot-reloaded via ``reload_gateway()``. Firestore is
updated on request when firebase-admin credentials are available.

Public API surface is stable across the v3 migration. Internals changed:
- ``load_config`` now parses ROBOT.md frontmatter (via PyYAML between ---
  fences), NOT a standalone .rcan.yaml file.
- ``get_loa_status`` reads ``frontmatter.safety.loa_enforcement`` /
  ``frontmatter.safety.min_loa_for_control`` rather than the flat keys of
  the old config format.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def get_config_path(override: str | None = None) -> Path:
    """Return the path to ROBOT.md (or ``$OPENCASTOR_CONFIG`` override)."""
    return Path(override or os.getenv("OPENCASTOR_CONFIG", "ROBOT.md"))


def load_config(config_path: Path) -> dict[str, Any]:
    """Load ROBOT.md frontmatter as a dict. Returns empty dict if no frontmatter."""
    import yaml  # type: ignore[import-untyped]

    text = Path(config_path).read_text()
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    body = text[4:end]
    return yaml.safe_load(body) or {}


def save_config(config: dict[str, Any], config_path: Path) -> None:
    """Re-emit ROBOT.md with updated frontmatter. Preserves body below the fence."""
    import yaml  # type: ignore[import-untyped]

    p = Path(config_path)
    existing = p.read_text() if p.exists() else "---\n---\n"
    if "\n---" in existing[4:]:
        body = existing.split("\n---", 2)[-1]
    else:
        body = ""
    serialized = yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True)
    p.write_text(f"---\n{serialized}---{body}")


def get_loa_status(config: dict[str, Any]) -> dict[str, Any]:
    """Return a status dict describing the LoA enforcement state.

    Reads ``safety.loa_enforcement`` and ``safety.min_loa_for_control`` from
    the frontmatter dict. Falls back to legacy top-level keys for any
    manifest still carrying them (pre-migration reads).
    """
    safety = config.get("safety") or {}
    loa_enforcement = safety.get("loa_enforcement", config.get("loa_enforcement", False))
    min_loa = int(safety.get("min_loa_for_control", config.get("min_loa_for_control", 1)))
    rcan_version = str(config.get("rcan_version", "unknown"))
    return {
        "loa_enforcement": bool(loa_enforcement),
        "min_loa_for_control": min_loa,
        "rcan_version": rcan_version,
        "loa_required": rcan_version >= "1.6",
    }


def set_loa_enforcement(
    config_path: Path,
    enabled: bool,
    min_loa: int | None = None,
) -> dict[str, Any]:
    """Patch ``safety.loa_enforcement`` / ``safety.min_loa_for_control`` on disk."""
    config = load_config(config_path)
    safety = dict(config.get("safety") or {})
    safety["loa_enforcement"] = enabled
    if min_loa is not None:
        safety["min_loa_for_control"] = min_loa
    config["safety"] = safety
    save_config(config, config_path)
    return get_loa_status(config)


def reload_gateway(gateway_url: str = "http://localhost:8001", token: str | None = None) -> bool:
    """Ask a running gateway to reload its manifest (POST /api/config/reload)."""
    import urllib.error
    import urllib.request

    token = token or os.getenv("OPENCASTOR_TOKEN", "")
    req = urllib.request.Request(
        f"{gateway_url}/api/config/reload",
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        data=b"{}",
    )
    try:
        with urllib.request.urlopen(req, timeout=5):
            return True
    except (urllib.error.URLError, OSError):
        return False


def push_loa_to_firestore(rrn: str, enabled: bool, min_loa: int = 1) -> bool:
    """Update loa_enforcement + min_loa_for_control in the Firestore robot doc."""
    try:
        from google.cloud import firestore  # type: ignore[import-untyped]
        from google.oauth2 import service_account  # type: ignore[import-untyped]

        sa_path = Path.home() / ".config" / "opencastor" / "firebase-sa-key.json"
        creds = service_account.Credentials.from_service_account_file(
            str(sa_path),
            scopes=["https://www.googleapis.com/auth/datastore"],
        )
        db = firestore.Client(project="opencastor", credentials=creds)
        db.collection("robots").document(rrn).update(
            {
                "loa_enforcement": enabled,
                "min_loa_for_control": min_loa,
            }
        )
        return True
    except Exception:
        return False
