"""
Integration test: run rcan-py validator against OpenCastor's RCAN YAML fixture.
Tests the full validation pipeline including schema checks.
"""

import json
import os
import pathlib
import re

import pytest
import yaml

FIXTURE_PATH = pathlib.Path(__file__).parent / "fixtures" / "sample.rcan.yaml"


def test_fixture_loads():
    """sample.rcan.yaml should be valid YAML."""
    assert FIXTURE_PATH.exists(), f"Fixture not found: {FIXTURE_PATH}"
    with open(FIXTURE_PATH) as f:
        config = yaml.safe_load(f)
    assert isinstance(config, dict)


def test_rcan_validate_config():
    """rcan-py validate_config should accept sample.rcan.yaml."""
    try:
        from rcan.validate import validate_config
    except ImportError:
        pytest.skip("rcan SDK not installed")

    with open(FIXTURE_PATH) as f:
        config = yaml.safe_load(f)

    result = validate_config(config)
    # validate_config returns either a (bool, list) tuple or a ValidationResult object
    if hasattr(result, "ok"):
        valid, errors = result.ok, result.issues
    else:
        valid, errors = result
    assert valid, f"Validation failed: {errors}"


def test_rcan_version_field():
    """rcan_version field must be present and in acceptable format."""
    with open(FIXTURE_PATH) as f:
        config = yaml.safe_load(f)

    rcan_version = config.get("rcan_version")
    assert rcan_version is not None
    assert re.match(r"^\d+\.\d+(\.\d+)?", rcan_version), f"Bad rcan_version: {rcan_version}"


def test_sdk_compat_check():
    """SDK compat check should run without crashing."""
    try:
        from castor.rcan.sdk_compat import check_sdk_compat

        result = check_sdk_compat()
        assert "compatible" in result
        assert "warnings" in result
        assert "info" in result
    except ImportError:
        pytest.skip("sdk_compat not available")


def test_commitment_chain_appended(tmp_path):
    """Commitment chain should append on action execution."""
    os.environ["OPENCASTOR_COMMITMENT_LOG"] = str(tmp_path / "test_commitments.jsonl")
    try:
        from castor.rcan.commitment_chain import CommitmentChain, reset_chain

        reset_chain()
        log_file = tmp_path / "test_commitments.jsonl"
        chain = CommitmentChain(secret="test-secret", log_path=log_file)
        chain.append_action("test", {"timestamp": "2026-03-06T00:00:00Z"})
        assert log_file.exists()
        entries = [json.loads(line) for line in log_file.read_text().strip().splitlines()]
        assert len(entries) == 1
        assert entries[0]["action"] == "test"
    except ImportError:
        pytest.skip("commitment_chain not available")
    finally:
        os.environ.pop("OPENCASTOR_COMMITMENT_LOG", None)
        try:
            from castor.rcan.commitment_chain import reset_chain

            reset_chain()
        except ImportError:
            pass
