"""
RCAN §21 Robot Registry Framework (RRF) protocol stubs.

Implements REGISTRY_REGISTER and REGISTRY_RESOLVE message types for
registering robots with the RRF and resolving Robot Registration Numbers (RRNs)
to Robot URIs (RURIs) and associated metadata.

Spec: https://rcan.dev/spec/section-21/
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from castor.rcan.message import MessageType


@dataclass
class RegistryMessage:
    """Payload for REGISTRY_REGISTER (§21.2).

    Sent by a robot to register itself with the RRF.

    Attributes:
        msg_id:     Unique message identifier (UUID).
        rrn:        Robot Registration Number (e.g. ``rrn://example.org/rover-1``).
        ruri:       Robot URI — the reachable endpoint for this robot.
        public_key: PEM-encoded public key for identity verification.
        timestamp:  Unix timestamp of registration request.
    """

    msg_id: str
    rrn: str
    ruri: str
    public_key: str
    timestamp: float = field(default_factory=time.time)

    def to_message(self) -> dict[str, Any]:
        """Serialize to RCAN message format using REGISTRY_REGISTER type."""
        return {
            "type": MessageType.REGISTRY_REGISTER,
            "msg_id": self.msg_id,
            "payload": {
                "rrn": self.rrn,
                "ruri": self.ruri,
                "public_key": self.public_key,
                "timestamp": self.timestamp,
            },
        }

    @classmethod
    def from_message(cls, data: dict[str, Any]) -> RegistryMessage:
        """Parse a REGISTRY_REGISTER message dict.

        Args:
            data: Raw message dict (as returned by ``to_message()``).

        Raises:
            ValueError: If any required field is missing.
        """
        payload = data.get("payload", data)
        required = ("rrn", "ruri", "public_key")
        for key in required:
            if key not in payload:
                raise ValueError(f"Missing required field: '{key}'")
        msg_id = data.get("msg_id") or str(uuid.uuid4())
        return cls(
            msg_id=msg_id,
            rrn=payload["rrn"],
            ruri=payload["ruri"],
            public_key=payload["public_key"],
            timestamp=payload.get("timestamp", time.time()),
        )


@dataclass
class RegistryResolveRequest:
    """Payload for REGISTRY_RESOLVE request (§21.3).

    Sent to the RRF to look up an RRN and retrieve RURI + metadata.

    Attributes:
        rrn:    Robot Registration Number to resolve.
        msg_id: Unique message identifier (UUID).
    """

    rrn: str
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_message(self) -> dict[str, Any]:
        """Serialize to RCAN message format using REGISTRY_RESOLVE type."""
        return {
            "type": MessageType.REGISTRY_RESOLVE,
            "msg_id": self.msg_id,
            "payload": {"rrn": self.rrn},
        }


@dataclass
class RegistryResolveResponse:
    """Payload for REGISTRY_RESOLVE response (§21.3).

    Returned by the RRF with resolved RURI and verification status.

    Attributes:
        rrn:      The Robot Registration Number that was resolved.
        ruri:     Resolved Robot URI (reachable endpoint).
        verified: Whether the robot's identity has been cryptographically verified.
        tier:     Service tier (e.g. ``'free'``, ``'pro'``, ``'enterprise'``).
    """

    rrn: str
    ruri: str
    verified: bool
    tier: str

    def to_message(self) -> dict[str, Any]:
        """Serialize to a response dict."""
        return {
            "type": MessageType.REGISTRY_RESOLVE,
            "payload": {
                "rrn": self.rrn,
                "ruri": self.ruri,
                "verified": self.verified,
                "tier": self.tier,
            },
        }
