"""castor.rcan3.signer — dict-level hybrid signing bound to a CastorIdentity.

All outgoing RCAN dict bodies (registrations, compliance artifacts) sign
through a single ``CastorSigner`` instance so the caller never needs to
pass the keypair directly.

The underlying ``rcan.sign_body`` produces a hybrid ML-DSA-65 + Ed25519
signature. The result dict contains ``sig``, ``pq_signing_pub``, ``pq_kid``
fields alongside the original body fields.
"""

from __future__ import annotations

import logging
from typing import Any

from rcan import sign_body, verify_body

from castor.rcan3.identity import CastorIdentity

logger = logging.getLogger("OpenCastor.Signer")


class CastorSigner:
    """A signer bound to a :class:`CastorIdentity` for the lifetime of a process."""

    def __init__(self, identity: CastorIdentity) -> None:
        self._identity = identity

    @property
    def public_key_jwk(self) -> dict[str, Any]:
        return self._identity.public_key_jwk

    @property
    def public_key_bytes(self) -> bytes:
        return self._identity.keypair.public_key_bytes

    def sign(self, body: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of ``body`` with hybrid signature fields attached.

        The returned dict includes ``sig``, ``pq_signing_pub``, and ``pq_kid``
        at the top level (as produced by ``rcan.sign_body``).
        """
        return sign_body(
            self._identity.keypair,
            body,
            ed25519_secret=self._identity.ed25519_secret,
            ed25519_public=self._identity.ed25519_public,
        )

    def verify(self, signed_body: dict[str, Any]) -> bool:
        """Verify ``signed_body`` against this signer's public key.

        Returns False on tamper/malformed signature (KeyError, ValueError,
        TypeError) rather than raising, so callers can surface a clean reject
        path.

        ImportError, ConnectionError, OSError and other environment failures
        propagate — they indicate an infrastructure problem, not a tamper event,
        and silently returning False would mask them.
        """
        try:
            return verify_body(signed_body, self._identity.keypair.public_key_bytes)
        except (KeyError, ValueError, TypeError) as e:
            # Malformed signature structure or body — treat as verification failure.
            logger.debug("signature verification rejected malformed input: %s", e)
            return False
        # ImportError / ConnectionError / OSError propagate — environment problem,
        # not a tamper event.
