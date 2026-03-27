"""LoA (Level of Assurance) enforcement management.

Provides CLI and API helpers to enable, disable, and report on LoA
enforcement for the RCAN Protocol 66 access control gate (GAP-16).

The canonical source of truth is the RCAN config file (.rcan.yaml).
A running bridge can be hot-reloaded without restart.
Firestore is updated when firebase-admin credentials are available.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# ── Config helpers ────────────────────────────────────────────────────────────


def get_config_path(override: str | None = None) -> Path:
    return Path(override or os.getenv("OPENCASTOR_CONFIG", "robot.rcan.yaml"))


def load_config(config_path: Path) -> dict[str, Any]:
    import yaml  # type: ignore[import-untyped]

    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def save_config(config: dict[str, Any], config_path: Path) -> None:
    import yaml  # type: ignore[import-untyped]

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ── Core LoA operations ───────────────────────────────────────────────────────


def get_loa_status(config: dict[str, Any]) -> dict[str, Any]:
    """Return a status dict describing the current LoA enforcement state."""
    return {
        "loa_enforcement": bool(config.get("loa_enforcement", False)),
        "min_loa_for_control": int(config.get("min_loa_for_control", 1)),
        "rcan_version": config.get("rcan_version", "unknown"),
        "loa_required": config.get("rcan_version", "0") >= "1.6",
    }


def set_loa_enforcement(
    config_path: Path,
    enabled: bool,
    min_loa: int | None = None,
) -> dict[str, Any]:
    """Patch the config file to enable or disable LoA enforcement.

    Returns the updated status dict.
    """
    config = load_config(config_path)
    config["loa_enforcement"] = enabled
    if min_loa is not None:
        config["min_loa_for_control"] = min_loa
    save_config(config, config_path)
    return get_loa_status(config)


# ── Gateway hot-reload ────────────────────────────────────────────────────────


def reload_gateway(gateway_url: str = "http://localhost:8001", token: str | None = None) -> bool:
    """Ask a running gateway to reload its config file (PATCH /api/config/reload)."""
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


# ── Firestore sync ────────────────────────────────────────────────────────────


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
