"""Tests for the 2.1 → 2.2 → 3.0 migration chain added in feat/rcan-3.0-alignment.

Note: ``migrate_config(config, dry_run=True)`` returns
``(migrated_config, changes_list)`` where ``changes_list`` contains human-readable
step descriptions like "Migrated 2.1 -> 2.2". The migration-emitted *warnings*
(about missing fields, deprecated algorithms, etc.) live INSIDE the migrated
config under the ``_migration_warnings`` key, not in the second tuple element.
"""

from __future__ import annotations

from castor.migrate import migrate_config


def test_migrate_2_1_to_2_2_bumps_version():
    config = {"rcan_version": "2.1", "metadata": {"robot_name": "test"}}
    migrated, _ = migrate_config(config, dry_run=True)
    # Full chain runs 2.1 → 2.2 → 3.0, so final version is 3.0
    # But until Task 3 adds the 2.2→3.0 hop, this test will see "2.2" instead.
    # We accept either here so Task 2 can pass standalone; Task 3's tests lock 3.0.
    assert migrated["rcan_version"] in ("2.2", "3.0"), (
        f"after 2.1→2.2 migration, expected rcan_version in (2.2, 3.0); got {migrated['rcan_version']!r}"
    )


def test_migrate_2_1_emits_signing_alg_warning():
    config = {"rcan_version": "2.1", "metadata": {"robot_name": "test"}}
    migrated, _ = migrate_config(config, dry_run=True)
    warnings = migrated.get("_migration_warnings", [])
    assert any("signing_alg" in w.lower() or "ml-dsa" in w.lower() for w in warnings), (
        f"expected warning about signing_alg; got warnings={warnings!r}"
    )


def test_migrate_2_1_preserves_operator_fields():
    config = {
        "rcan_version": "2.1",
        "metadata": {"robot_name": "bob", "rrn": "RRN-000000000001"},
        "agent": {"model": "claude-sonnet-4-6"},
        "drivers": [{"id": "arm", "protocol": "feetech"}],
    }
    migrated, _ = migrate_config(config, dry_run=True)
    assert migrated["metadata"]["robot_name"] == "bob"
    assert migrated["metadata"]["rrn"] == "RRN-000000000001"
    assert migrated["agent"]["model"] == "claude-sonnet-4-6"
    assert migrated["drivers"] == [{"id": "arm", "protocol": "feetech"}]


def test_migrate_2_1_to_2_2_changelog_entry():
    config = {"rcan_version": "2.1", "metadata": {"robot_name": "test"}}
    _, changes = migrate_config(config, dry_run=True)
    assert any("2.1" in c and "2.2" in c for c in changes), (
        f"expected a '2.1 -> 2.2' changelog entry; got changes={changes!r}"
    )
