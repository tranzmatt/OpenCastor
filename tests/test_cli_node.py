"""Tests for castor node CLI subcommands (Issue #497)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _make_args(**kwargs):
    """Build a SimpleNamespace args object for cmd_node."""
    defaults = {"node_cmd": None}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _import_cmd_node():
    from castor.cli import cmd_node

    return cmd_node


class TestNodeStatus:
    def test_status_prints_manifest(self, capsys):
        cmd_node = _import_cmd_node()
        mock_config = MagicMock()
        mock_broadcaster = MagicMock()
        mock_broadcaster.get_manifest.return_value = {
            "node_type": "resolver",
            "operator": "acme-robotics",
            "namespace_prefix": "RRN",
            "api_base": "https://api.acme.example",
            "capabilities": ["resolve", "cache"],
            "last_sync": "2026-03-06T12:00:00Z",
        }

        with (
            patch("castor.rcan.node_broadcaster.NodeConfig", return_value=mock_config),
            patch("castor.rcan.node_broadcaster.NodeBroadcaster", return_value=mock_broadcaster),
        ):
            cmd_node(_make_args(node_cmd="status"))

        captured = capsys.readouterr()
        assert "RCAN Node Status:" in captured.out
        assert "resolver" in captured.out
        assert "acme-robotics" in captured.out
        assert "resolve, cache" in captured.out

    def test_status_handles_exception(self, capsys):
        cmd_node = _import_cmd_node()
        with patch(
            "castor.rcan.node_broadcaster.NodeBroadcaster",
            side_effect=RuntimeError("boom"),
        ):
            cmd_node(_make_args(node_cmd="status"))

        captured = capsys.readouterr()
        assert "Error" in captured.err or "Error" in captured.out

    def test_status_operator_not_set(self, capsys):
        cmd_node = _import_cmd_node()
        mock_broadcaster = MagicMock()
        mock_broadcaster.get_manifest.return_value = {
            "node_type": "resolver",
            "operator": "",
            "namespace_prefix": "RRN",
            "api_base": "",
            "capabilities": ["resolve"],
            "last_sync": "2026-03-06T00:00:00Z",
        }

        with (
            patch("castor.rcan.node_broadcaster.NodeConfig", return_value=MagicMock()),
            patch("castor.rcan.node_broadcaster.NodeBroadcaster", return_value=mock_broadcaster),
        ):
            cmd_node(_make_args(node_cmd="status"))

        captured = capsys.readouterr()
        assert "(not set)" in captured.out


class TestNodeManifest:
    def test_manifest_outputs_json(self, capsys):
        cmd_node = _import_cmd_node()
        mock_broadcaster = MagicMock()
        mock_broadcaster.get_manifest.return_value = {
            "rcan_node_version": "1.0",
            "node_type": "resolver",
            "operator": "test",
            "namespace_prefix": "RRN",
            "api_base": "",
            "capabilities": ["resolve"],
            "last_sync": "2026-03-06T00:00:00Z",
        }

        with (
            patch("castor.rcan.node_broadcaster.NodeConfig", return_value=MagicMock()),
            patch("castor.rcan.node_broadcaster.NodeBroadcaster", return_value=mock_broadcaster),
        ):
            cmd_node(_make_args(node_cmd="manifest"))

        import json

        captured = capsys.readouterr()
        # Should be valid JSON
        data = json.loads(captured.out)
        assert data["node_type"] == "resolver"
        assert "capabilities" in data

    def test_manifest_handles_exception(self, capsys):
        cmd_node = _import_cmd_node()
        with patch(
            "castor.rcan.node_broadcaster.NodeBroadcaster",
            side_effect=ImportError("depthai not found"),
        ):
            cmd_node(_make_args(node_cmd="manifest"))

        captured = capsys.readouterr()
        assert "Error" in captured.err or "Error" in captured.out


class TestNodeResolve:
    def test_resolve_prints_robot_info(self, capsys):
        cmd_node = _import_cmd_node()
        mock_robot = MagicMock()
        mock_robot.manufacturer = "Acme"
        mock_robot.model = "Pioneer-3"
        mock_robot.attestation = "active"
        mock_robot.resolved_by = "https://rcan.dev"
        mock_robot.from_cache = False
        mock_robot.stale = False

        with patch("castor.rcan.node_resolver.NodeResolver") as MockResolver:
            MockResolver.return_value.resolve.return_value = mock_robot
            cmd_node(_make_args(node_cmd="resolve", rrn="RRN-AB-00000001"))

        captured = capsys.readouterr()
        assert "RRN-AB-00000001" in captured.out
        assert "Acme" in captured.out
        assert "Pioneer-3" in captured.out
        assert "live" in captured.out

    def test_resolve_shows_cache_source(self, capsys):
        cmd_node = _import_cmd_node()
        mock_robot = MagicMock()
        mock_robot.manufacturer = "Clearpath"
        mock_robot.model = "Husky"
        mock_robot.attestation = "active"
        mock_robot.resolved_by = "https://rcan.dev"
        mock_robot.from_cache = True
        mock_robot.stale = False

        with patch("castor.rcan.node_resolver.NodeResolver") as MockResolver:
            MockResolver.return_value.resolve.return_value = mock_robot
            cmd_node(_make_args(node_cmd="resolve", rrn="RRN-CP-00000002"))

        captured = capsys.readouterr()
        assert "cache" in captured.out

    def test_resolve_shows_stale_source(self, capsys):
        cmd_node = _import_cmd_node()
        mock_robot = MagicMock()
        mock_robot.manufacturer = "Boston Dynamics"
        mock_robot.model = "Spot"
        mock_robot.attestation = "active"
        mock_robot.resolved_by = "https://rcan.dev"
        mock_robot.from_cache = True
        mock_robot.stale = True

        with patch("castor.rcan.node_resolver.NodeResolver") as MockResolver:
            MockResolver.return_value.resolve.return_value = mock_robot
            cmd_node(_make_args(node_cmd="resolve", rrn="RRN-BD-00000003"))

        captured = capsys.readouterr()
        assert "stale cache" in captured.out

    def test_resolve_error_exits_1(self):
        cmd_node = _import_cmd_node()
        with patch("castor.rcan.node_resolver.NodeResolver") as MockResolver:
            MockResolver.return_value.resolve.side_effect = RuntimeError("not found")
            try:
                cmd_node(_make_args(node_cmd="resolve", rrn="RRN-XX-99999999"))
                raised = False
            except SystemExit as e:
                raised = True
                assert e.code == 1
        assert raised

    def test_resolve_no_rrn_prints_usage(self, capsys):
        cmd_node = _import_cmd_node()
        cmd_node(_make_args(node_cmd="resolve", rrn=None))
        captured = capsys.readouterr()
        assert "Usage" in captured.out


class TestNodePing:
    def test_ping_reachable(self, capsys):
        cmd_node = _import_cmd_node()
        with patch("castor.rcan.node_resolver.NodeResolver") as MockResolver:
            MockResolver.return_value.is_reachable.return_value = (True, 42.5)
            cmd_node(_make_args(node_cmd="ping"))

        captured = capsys.readouterr()
        assert "reachable" in captured.out
        assert "42" in captured.out

    def test_ping_unreachable_exits_1(self, capsys):
        cmd_node = _import_cmd_node()
        with patch("castor.rcan.node_resolver.NodeResolver") as MockResolver:
            MockResolver.return_value.is_reachable.return_value = (False, 5000.0)
            try:
                cmd_node(_make_args(node_cmd="ping"))
                raised = False
            except SystemExit as e:
                raised = True
                assert e.code == 1
        assert raised
        captured = capsys.readouterr()
        assert "unreachable" in captured.out

    def test_ping_import_error(self, capsys):
        cmd_node = _import_cmd_node()
        with patch("castor.rcan.node_resolver.NodeResolver", side_effect=ImportError("no rcan")):
            cmd_node(_make_args(node_cmd="ping"))

        captured = capsys.readouterr()
        assert "no rcan" in captured.err


class TestNodeUnknownCmd:
    def test_unknown_cmd_prints_usage(self, capsys):
        cmd_node = _import_cmd_node()
        cmd_node(_make_args(node_cmd="unknown"))
        captured = capsys.readouterr()
        assert "Usage" in captured.out

    def test_no_cmd_prints_usage(self, capsys):
        cmd_node = _import_cmd_node()
        cmd_node(_make_args(node_cmd=None))
        captured = capsys.readouterr()
        assert "Usage" in captured.out
