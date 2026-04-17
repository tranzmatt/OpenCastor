"""Regression test: every module that declares an RCAN protocol version must agree."""

from __future__ import annotations

from castor.compliance import SPEC_VERSION as COMPLIANCE_SPEC_VERSION
from castor.migrate import CURRENT_VERSION as MIGRATE_CURRENT_VERSION
from castor.rcan.message import RCAN_SPEC_VERSION as MESSAGE_SPEC_VERSION


EXPECTED = "3.0"


def test_compliance_spec_version_is_3_0():
    assert COMPLIANCE_SPEC_VERSION == EXPECTED, (
        f"compliance.SPEC_VERSION = {COMPLIANCE_SPEC_VERSION!r}; expected {EXPECTED!r}"
    )


def test_rcan_message_spec_version_matches_compliance():
    assert MESSAGE_SPEC_VERSION == COMPLIANCE_SPEC_VERSION, (
        f"castor.rcan.message.RCAN_SPEC_VERSION = {MESSAGE_SPEC_VERSION!r} "
        f"does not match castor.compliance.SPEC_VERSION = {COMPLIANCE_SPEC_VERSION!r}. "
        f"Both must be bumped together when advancing the protocol."
    )


def test_migrate_current_version_matches_compliance():
    assert MIGRATE_CURRENT_VERSION == COMPLIANCE_SPEC_VERSION, (
        f"castor.migrate.CURRENT_VERSION = {MIGRATE_CURRENT_VERSION!r} "
        f"does not match castor.compliance.SPEC_VERSION = {COMPLIANCE_SPEC_VERSION!r}. "
        f"When you bump SPEC_VERSION you must also add the migration chain to the new version."
    )
