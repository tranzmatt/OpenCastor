"""Tests for castor.init_wizard — ROBOT.md emission."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def test_cmd_init_writes_robot_md(tmp_path, monkeypatch):
    """cmd_init writes a ROBOT.md with v3.2 frontmatter to the given path."""
    from castor.init_wizard import cmd_init

    ns = argparse.Namespace(
        non_interactive=True,
        path=str(tmp_path / "ROBOT.md"),
        robot_name="bob",
        manufacturer="craigm26",
        model="so-arm101",
        version="1.0.0",
        device_id="bob-001",
        provider="anthropic",
        llm_model="claude-sonnet-4-6",
    )
    rc = cmd_init(ns)
    assert rc == 0

    md = (tmp_path / "ROBOT.md").read_text()
    assert md.startswith("---\n")
    # Parse frontmatter
    _, front, _ = md.split("---", 2)
    fm = yaml.safe_load(front)
    assert fm["rcan_version"] == "3.2"
    assert fm["metadata"]["robot_name"] == "bob"
    assert fm["agent"]["runtimes"][0]["id"] == "opencastor"
    assert fm["agent"]["runtimes"][0]["harness"] == "castor-default"
    assert fm["agent"]["runtimes"][0]["default"] is True


def test_cmd_init_refuses_overwrite_without_force(tmp_path):
    from castor.init_wizard import cmd_init

    p = tmp_path / "ROBOT.md"
    p.write_text("---\nrcan_version: '3.2'\n---\n")

    ns = argparse.Namespace(
        non_interactive=True,
        path=str(p),
        robot_name="b",
        manufacturer="a",
        model="c",
        version="1.0",
        device_id="d",
        provider="anthropic",
        llm_model="claude",
    )
    rc = cmd_init(ns)
    assert rc != 0  # non-zero exit code


def test_cmd_init_force_overwrites(tmp_path):
    from castor.init_wizard import cmd_init

    p = tmp_path / "ROBOT.md"
    p.write_text("old")

    ns = argparse.Namespace(
        non_interactive=True,
        path=str(p),
        robot_name="b",
        manufacturer="a",
        model="c",
        version="1.0",
        device_id="d",
        provider="anthropic",
        llm_model="claude",
        force=True,
    )
    rc = cmd_init(ns)
    assert rc == 0
    assert "rcan_version" in p.read_text()


def test_cmd_quickstart_is_available():
    """cmd_quickstart is the second CLI entry point — must still be importable."""
    from castor.init_wizard import cmd_quickstart

    assert callable(cmd_quickstart)


def test_emitted_robot_md_round_trips_through_rcan_py(tmp_path):
    """rcan.from_manifest parses our output and finds the runtime."""
    from rcan import from_manifest

    from castor.init_wizard import cmd_init

    ns = argparse.Namespace(
        non_interactive=True,
        path=str(tmp_path / "ROBOT.md"),
        robot_name="bob",
        manufacturer="craigm26",
        model="so-arm101",
        version="1.0.0",
        device_id="bob-001",
        provider="anthropic",
        llm_model="claude-sonnet-4-6",
    )
    cmd_init(ns)
    info = from_manifest(tmp_path / "ROBOT.md")
    assert info.robot_name == "bob"
    assert info.rcan_version == "3.2"
    assert info.agent_runtimes is not None
    assert info.agent_runtimes[0]["id"] == "opencastor"


def test_init_and_quickstart_in_cli_help():
    """castor --help output must mention init and quickstart."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "castor", "--help"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    combined = result.stdout + result.stderr
    assert "init" in combined, "'init' not found in castor --help"
    assert "quickstart" in combined, "'quickstart' not found in castor --help"
