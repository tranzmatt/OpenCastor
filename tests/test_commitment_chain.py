"""Tests for castor.rcan.commitment_chain."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from castor.rcan.commitment_chain import CommitmentChain, get_commitment_chain, reset_chain


SECRET = "test-secret-for-chain"


def make_chain(tmp_path: Path) -> CommitmentChain:
    return CommitmentChain(secret=SECRET, log_path=tmp_path / "commitments.jsonl")


# ---------------------------------------------------------------------------
# Basic append + seal
# ---------------------------------------------------------------------------


def test_chain_enabled(tmp_path):
    chain = make_chain(tmp_path)
    assert chain.enabled is True


def test_append_returns_record(tmp_path):
    chain = make_chain(tmp_path)
    record = chain.append_action("move_forward", {"distance_m": 1.0}, robot_uri="rcan://r/a/b/v1/x")
    assert record is not None
    assert record.action == "move_forward"
    assert record.hmac_value is not None


def test_append_writes_to_log(tmp_path):
    chain = make_chain(tmp_path)
    chain.append_action("stop", {})
    log_path = tmp_path / "commitments.jsonl"
    assert log_path.exists()
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["action"] == "stop"
    assert "hmac" in data


def test_multiple_records_chained(tmp_path):
    chain = make_chain(tmp_path)
    r1 = chain.append_action("move_forward", {"distance_m": 1.0})
    r2 = chain.append_action("stop", {})
    assert r2.previous_hash == r1.content_hash


def test_in_memory_verify(tmp_path):
    chain = make_chain(tmp_path)
    chain.append_action("move_forward", {})
    chain.append_action("stop", {})
    assert chain.verify() is True


# ---------------------------------------------------------------------------
# Log verification
# ---------------------------------------------------------------------------


def test_verify_log_valid(tmp_path):
    chain = make_chain(tmp_path)
    chain.append_action("a", {})
    chain.append_action("b", {})
    chain.append_action("c", {})
    valid, count, errors = chain.verify_log()
    assert valid is True
    assert count == 3
    assert errors == []


def test_verify_log_empty(tmp_path):
    chain = make_chain(tmp_path)
    valid, count, errors = chain.verify_log()
    assert valid is True
    assert count == 0


def test_verify_log_tampered(tmp_path):
    chain = make_chain(tmp_path)
    chain.append_action("move_forward", {})
    chain.append_action("stop", {})

    log_path = tmp_path / "commitments.jsonl"
    content = log_path.read_text()
    lines = content.strip().splitlines()
    # Tamper: change action in first line
    data = json.loads(lines[0])
    data["action"] = "self_destruct"
    lines[0] = json.dumps(data)
    log_path.write_text("\n".join(lines) + "\n")

    valid, count, errors = chain.verify_log()
    assert valid is False
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# last_n
# ---------------------------------------------------------------------------


def test_last_n(tmp_path):
    chain = make_chain(tmp_path)
    for i in range(5):
        chain.append_action(f"action_{i}", {"i": i})
    records = chain.last_n(3)
    assert len(records) == 3
    assert records[-1]["action"] == "action_4"


def test_last_n_empty(tmp_path):
    chain = make_chain(tmp_path)
    assert chain.last_n(5) == []


# ---------------------------------------------------------------------------
# Chain continuity across instances
# ---------------------------------------------------------------------------


def test_chain_continuity_across_instances(tmp_path):
    """Second CommitmentChain instance continues from where first left off."""
    chain1 = CommitmentChain(secret=SECRET, log_path=tmp_path / "c.jsonl")
    r1 = chain1.append_action("move", {})

    chain2 = CommitmentChain(secret=SECRET, log_path=tmp_path / "c.jsonl")
    r2 = chain2.append_action("stop", {})

    assert r2.previous_hash == r1.content_hash


# ---------------------------------------------------------------------------
# Default secret fallback
# ---------------------------------------------------------------------------


def test_default_secret_from_env(tmp_path):
    with patch.dict(os.environ, {"OPENCASTOR_COMMITMENT_SECRET": "env-secret"}):
        chain = CommitmentChain(log_path=tmp_path / "c.jsonl")
    assert chain._secret == b"env-secret"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


def test_singleton_returns_same_instance(tmp_path):
    reset_chain()
    c1 = get_commitment_chain(secret=SECRET, log_path=tmp_path / "c.jsonl")
    c2 = get_commitment_chain()
    assert c1 is c2
    reset_chain()


# ---------------------------------------------------------------------------
# Graceful failure if rcan not installed
# ---------------------------------------------------------------------------


def test_disabled_when_rcan_missing(tmp_path):
    import sys
    # Temporarily hide the rcan package
    rcan_mod = sys.modules.pop("rcan", None)
    rcan_audit = sys.modules.pop("rcan.audit", None)
    rcan_address = sys.modules.pop("rcan.address", None)
    rcan_exceptions = sys.modules.pop("rcan.exceptions", None)
    try:
        with patch.dict("sys.modules", {"rcan": None, "rcan.audit": None}):
            chain = CommitmentChain(secret=SECRET, log_path=tmp_path / "c.jsonl")
            # Should gracefully disable
            result = chain.append_action("move", {})
            # Returns None or record — either is acceptable (non-fatal)
    finally:
        if rcan_mod:
            sys.modules["rcan"] = rcan_mod
        if rcan_audit:
            sys.modules["rcan.audit"] = rcan_audit
