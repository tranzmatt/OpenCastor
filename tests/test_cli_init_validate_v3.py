"""Tests for the v3.0 `castor init` and `castor validate` CLI gap fixes.

- `castor init` argparse now produces the Namespace shape init_wizard.cmd_init
  expects (path, robot_name, manufacturer, model, version, device_id,
  provider, llm_model, non_interactive, force).
- `castor validate <ROBOT.md>` detects the frontmatter-markdown format and
  delegates to `rcan.from_manifest`, rather than feeding markdown to
  `yaml.safe_load` (which errors on the dual-document stream).
"""

from __future__ import annotations

import argparse

import castor.cli as cli


def _build_parser() -> argparse.ArgumentParser:
    """Build the v3.0 top-level argparse by running the main() registration
    block up to and including the subparsers. We invoke main() via a hard
    --help so argparse raises SystemExit after it has constructed the full
    subparser tree — we then retrieve the parser via the captured reference.
    """
    # Simpler: replicate the minimal subset by invoking main with a harmless
    # subcommand that parses in isolation. We just need the parser object
    # for inspection-style tests, so catch the SystemExit from argparse.

    parser = argparse.ArgumentParser()
    # Rebuild by calling main — but main builds locally. Instead, parse via
    # sys.argv and assert behaviour. This keeps the test hermetic.
    return parser


class TestCastorInitArgparseV3:
    """The `castor init` subparser now matches init_wizard.cmd_init's signature."""

    def test_init_parses_new_flags(self, monkeypatch):
        """Full v3.0 flag set should parse to a Namespace with the expected attrs."""
        import sys

        calls: list[argparse.Namespace] = []

        def _fake_wizard(ns):
            calls.append(ns)
            return 0

        monkeypatch.setattr("castor.init_wizard.cmd_init", _fake_wizard)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "castor",
                "init",
                "--path",
                "/tmp/ROBOT.md",
                "--robot-name",
                "bob",
                "--manufacturer",
                "SeeedStudio",
                "--model",
                "SO-ARM101",
                "--version",
                "1.0.0",
                "--device-id",
                "bob-001",
                "--provider",
                "anthropic",
                "--llm-model",
                "claude-sonnet-4-6",
                "--non-interactive",
                "--force",
            ],
        )
        cli.main()
        assert len(calls) == 1
        ns = calls[0]
        assert ns.path == "/tmp/ROBOT.md"
        assert ns.robot_name == "bob"
        assert ns.manufacturer == "SeeedStudio"
        assert ns.model == "SO-ARM101"
        assert ns.version == "1.0.0"
        assert ns.device_id == "bob-001"
        assert ns.provider == "anthropic"
        assert ns.llm_model == "claude-sonnet-4-6"
        assert ns.non_interactive is True
        assert ns.force is True

    def test_init_defaults(self, monkeypatch):
        """Bare `castor init` should parse with safe defaults."""
        import sys

        calls: list[argparse.Namespace] = []

        def _fake_wizard(ns):
            calls.append(ns)
            return 0

        monkeypatch.setattr("castor.init_wizard.cmd_init", _fake_wizard)
        monkeypatch.setattr(sys, "argv", ["castor", "init", "--non-interactive"])
        cli.main()
        ns = calls[0]
        assert ns.path == "ROBOT.md"
        assert ns.non_interactive is True
        assert ns.force is False


class TestCastorValidateRobotMd:
    """`castor validate ROBOT.md` delegates to rcan.from_manifest."""

    _FM = (
        "---\n"
        "rcan_version: '3.2'\n"
        "metadata:\n"
        "  robot_name: bob\n"
        "agent:\n"
        "  runtimes:\n"
        "    - id: opencastor\n"
        "      harness: castor-default\n"
        "      default: true\n"
        "      models: []\n"
        "---\n\n# bob\n\nA test robot.\n"
    )

    def test_positional_robot_md_validates(self, tmp_path, capsys):
        """castor validate <ROBOT.md> should detect frontmatter + print a ✓ line."""
        manifest = tmp_path / "ROBOT.md"
        manifest.write_text(self._FM)
        ns = argparse.Namespace(
            manifest=str(manifest),
            config="robot.rcan.yaml",
        )
        cli.cmd_validate(ns)
        out = capsys.readouterr().out
        assert "✓" in out
        assert "rcan_version: 3.2" in out
        assert "opencastor" in out

    def test_extensionless_markdown_is_sniffed(self, tmp_path, capsys):
        """Files without .md extension but with leading `---` fence also parse."""
        manifest = tmp_path / "bob-manifest"
        manifest.write_text(self._FM)
        ns = argparse.Namespace(manifest=str(manifest), config="x.rcan.yaml")
        cli.cmd_validate(ns)
        out = capsys.readouterr().out
        assert "✓" in out
        assert "runtimes: ['opencastor']" in out

    def test_json_mode_emits_manifest_shape(self, tmp_path, capsys):
        """--json should emit a machine-readable summary."""
        import json

        manifest = tmp_path / "ROBOT.md"
        manifest.write_text(self._FM)
        ns = argparse.Namespace(
            manifest=str(manifest),
            config="x.rcan.yaml",
            json=True,
        )
        cli.cmd_validate(ns)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["rcan_version"] == "3.2"
        assert data["ok"] is True
        assert data["agent_runtimes"][0]["id"] == "opencastor"
