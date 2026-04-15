"""castor/delegation.py — RCAN delegation chain management (§delegation)."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

MAX_DELEGATION_DEPTH = 3


@dataclass
class DelegationHop:
    robot_rrn: str
    scope: str
    issued_at: str
    expires_at: str
    sig: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def validate_chain(chain: list[Any]) -> None:
    if len(chain) > MAX_DELEGATION_DEPTH:
        raise ValueError(
            f"RCAN: delegation chain max depth is {MAX_DELEGATION_DEPTH}, got {len(chain)}"
        )


def build_hop(robot_rrn: str, scope: str, ttl_seconds: int = 3600) -> dict:
    now = time.time()
    return {
        "robot_rrn": robot_rrn,
        "scope": scope,
        "issued_at": str(int(now)),
        "expires_at": str(int(now + ttl_seconds)),
        "sig": "",  # Populated by signing layer
    }


def verify_chain(chain: list[Any], expected_rrn: str = "") -> bool:
    """Verify delegation chain structure and expiry. Signature verification is a stub."""
    try:
        validate_chain(chain)
    except ValueError:
        return False

    import logging

    _log = logging.getLogger(__name__)
    now = time.time()

    for i, hop in enumerate(chain):
        if isinstance(hop, dict):
            expires_at = hop.get("expires_at")
        elif hasattr(hop, "expires_at"):
            expires_at = hop.expires_at
        else:
            expires_at = None

        if expires_at is not None:
            try:
                if float(expires_at) < now:
                    _log.warning(
                        "RCAN: delegation chain hop %d expired at %s (now=%s)",
                        i,
                        expires_at,
                        int(now),
                    )
                    return False
            except (ValueError, TypeError):
                pass  # non-numeric expires_at — skip expiry check

    # Signature verification deferred pending full key-rotation infrastructure
    _log.debug("RCAN: delegation chain structure/expiry valid (signature verification pending)")
    return True
