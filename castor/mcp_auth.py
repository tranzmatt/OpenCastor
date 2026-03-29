"""castor/mcp_auth.py — MCP client auth: token → LoA resolution.

Tokens are declared in the robot's RCAN yaml under ``mcp_clients:``:

.. code-block:: yaml

    mcp_clients:
      - name: "claude-code-laptop"
        token_hash: "sha256:abc123..."   # sha256 hex digest of the raw token
        loa: 3
      - name: "codex-read-only"
        token_hash: "sha256:def456..."
        loa: 0

Token hashes are stored (never raw tokens), so the yaml is safe to commit
(assuming the tokens themselves are kept secret).

Auth is provider-agnostic: any MCP client — Claude Code, Codex, Cursor,
Gemini CLI, a cron job — gets the LoA associated with its token.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path
from typing import Any

import yaml

# Default LoA when no mcp_clients block is found and the server runs with
# --dev / CASTOR_MCP_DEV=1 (local-only, never exposed remotely).
_DEV_LOA = 3
_DEV_TOKEN = "dev"


def _hash_token(token: str) -> str:
    return "sha256:" + hashlib.sha256(token.encode()).hexdigest()


def resolve_loa(token: str, config_path: Path | None = None) -> int | None:
    """Return the LoA for *token*, or None if the token is not recognised.

    Parameters
    ----------
    token:
        Raw bearer token supplied by the MCP client.
    config_path:
        Path to the RCAN yaml.  Defaults to ``~/opencastor/bob.rcan.yaml``
        or ``CASTOR_CONFIG`` env var.
    """
    # Dev shortcut — only active when CASTOR_MCP_DEV is explicitly set.
    if os.environ.get("CASTOR_MCP_DEV") == "1" and token == _DEV_TOKEN:
        return _DEV_LOA

    if config_path is None:
        config_path = Path(
            os.environ.get("CASTOR_CONFIG", Path.home() / "opencastor/bob.rcan.yaml")
        )

    try:
        cfg: dict[str, Any] = yaml.safe_load(config_path.read_text()) or {}
    except Exception:
        return None

    clients: list[dict[str, Any]] = cfg.get("mcp_clients", [])
    token_hash = _hash_token(token)

    for client in clients:
        stored = client.get("token_hash", "")
        # Constant-time comparison to prevent timing attacks.
        if secrets.compare_digest(stored, token_hash):
            return int(client.get("loa", 0))

    return None


def generate_token(name: str, loa: int, config_path: Path) -> str:
    """Generate a new random token, append it to the yaml, return raw token."""
    raw = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw)

    try:
        cfg: dict[str, Any] = yaml.safe_load(config_path.read_text()) or {}
    except Exception:
        cfg = {}

    clients: list[dict[str, Any]] = cfg.setdefault("mcp_clients", [])
    # Remove any existing entry with the same name.
    cfg["mcp_clients"] = [c for c in clients if c.get("name") != name]
    cfg["mcp_clients"].append({"name": name, "token_hash": token_hash, "loa": loa})

    config_path.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))
    return raw


def list_clients(config_path: Path) -> list[dict[str, Any]]:
    """Return mcp_clients list from yaml (token hashes only, never raw)."""
    try:
        cfg = yaml.safe_load(config_path.read_text()) or {}
    except Exception:
        return []
    return cfg.get("mcp_clients", [])
