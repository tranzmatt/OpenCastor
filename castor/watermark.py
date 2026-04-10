"""
castor.watermark — AI output watermark tokens (RCAN §16.5).

Embeds a cryptographic watermark in every AI-generated COMMAND payload so
AI-produced commands are machine-detectable per EU AI Act Art. 50.

Token format: rcan-wm-v1:{hex(hmac_sha256(rrn:thought_id:timestamp, key)[:16])}
"""
from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any

WATERMARK_VERSION = "rcan-wm-v1"
WATERMARK_PATTERN = re.compile(r"^rcan-wm-v1:[0-9a-f]{32}$")


def compute_watermark_token(
    rrn: str,
    thought_id: str,
    timestamp: str,
    private_key_bytes: bytes,
) -> str:
    """Compute RCAN AI output watermark token per §16.5.

    Args:
        rrn: Robot Resource Name (e.g. ``"RRN-000000000001"``).
        thought_id: Unique ID of the Thought that produced the command.
        timestamp: ISO-8601 timestamp of the Thought (from ``thought.timestamp.isoformat()``).
        private_key_bytes: ML-DSA-65 private key bytes — the HMAC secret.

    Returns:
        Token string, e.g. ``"rcan-wm-v1:a3f9c1d2b8e47f20a3f9c1d2b8e47f20"``.
    """
    message = f"{rrn}:{thought_id}:{timestamp}".encode()
    digest = hmac.new(private_key_bytes, message, hashlib.sha256).digest()
    return f"{WATERMARK_VERSION}:{digest[:16].hex()}"


def verify_token_format(token: str) -> bool:
    """Return True if *token* matches ``rcan-wm-v1:{32 hex chars}``."""
    return bool(WATERMARK_PATTERN.match(token))


def verify_watermark_token(token: str, audit_log: Any) -> dict | None:
    """Look up *token* in the audit HMAC index.

    Args:
        token: Watermark token string to look up.
        audit_log: An ``AuditLog`` instance (or any object with ``_watermark_index: dict``).

    Returns:
        The full audit entry dict if found, else ``None``.
    """
    if not verify_token_format(token):
        return None
    index = getattr(audit_log, "_watermark_index", None)
    if index is None:
        return None
    return index.get(token)
