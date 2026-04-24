"""Tests for castor.loa after v3 ROBOT.md migration."""

from __future__ import annotations

import textwrap
from pathlib import Path


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "ROBOT.md"
    p.write_text(body)
    return p


def test_get_loa_status_reads_rcan_version_from_manifest(tmp_path):
    from castor.loa import get_loa_status, load_config

    p = _write(
        tmp_path,
        textwrap.dedent("""\
        ---
        rcan_version: "3.2"
        metadata:
          robot_name: bob
        safety:
          loa_enforcement: true
          min_loa_for_control: 2
        ---
    """),
    )
    config = load_config(p)
    status = get_loa_status(config)
    assert status["loa_enforcement"] is True
    assert status["min_loa_for_control"] == 2
    assert status["rcan_version"] == "3.2"


def test_set_loa_enforcement_round_trips(tmp_path):
    from castor.loa import get_loa_status, load_config, set_loa_enforcement

    p = _write(
        tmp_path,
        textwrap.dedent("""\
        ---
        rcan_version: "3.2"
        metadata:
          robot_name: bob
        safety: {}
        ---
    """),
    )
    updated = set_loa_enforcement(p, enabled=True, min_loa=3)
    assert updated["loa_enforcement"] is True
    assert updated["min_loa_for_control"] == 3

    # Reload and confirm persisted:
    again = get_loa_status(load_config(p))
    assert again["loa_enforcement"] is True
    assert again["min_loa_for_control"] == 3


def test_get_config_path_default_is_robot_md(monkeypatch):
    from castor.loa import get_config_path

    monkeypatch.delenv("OPENCASTOR_CONFIG", raising=False)
    p = get_config_path()
    assert p.name == "ROBOT.md"
