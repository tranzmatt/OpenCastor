"""Tests for castor.rcan.node_broadcaster (RCAN §17)."""

from __future__ import annotations

from castor.rcan.node_broadcaster import NodeBroadcaster, NodeConfig

REQUIRED_MANIFEST_KEYS = {
    "rcan_node_version",
    "node_type",
    "operator",
    "namespace_prefix",
    "public_key",
    "api_base",
    "capabilities",
    "sync_endpoint",
    "last_sync",
    "ttl_seconds",
    "contact",
    "sync_from",
}


# ── NodeConfig ────────────────────────────────────────────────────────────────


class TestNodeConfig:
    def test_defaults(self):
        cfg = NodeConfig()
        assert cfg.node_type == "resolver"
        assert cfg.capabilities == ["resolve"]
        assert cfg.sync_from == "https://rcan.dev/api/v1"

    def test_from_rcan_yaml_full(self):
        yaml_data = {
            "metadata": {"manufacturer": "AcmeCorp"},
            "rcan_protocol": {"api_base": "https://robots.acme.com/rcan"},
        }
        cfg = NodeConfig.from_rcan_yaml(yaml_data)
        assert cfg.operator == "AcmeCorp"
        assert cfg.api_base == "https://robots.acme.com/rcan"

    def test_from_rcan_yaml_missing_metadata(self):
        cfg = NodeConfig.from_rcan_yaml({})
        assert cfg.operator == ""
        assert cfg.api_base == ""

    def test_from_rcan_yaml_missing_rcan_protocol(self):
        cfg = NodeConfig.from_rcan_yaml({"metadata": {"manufacturer": "Foo"}})
        assert cfg.operator == "Foo"
        assert cfg.api_base == ""

    def test_from_rcan_yaml_preserves_defaults(self):
        cfg = NodeConfig.from_rcan_yaml({})
        assert cfg.node_type == "resolver"
        assert cfg.capabilities == ["resolve"]
        assert cfg.ttl_seconds == 3600


# ── NodeBroadcaster.get_manifest ──────────────────────────────────────────────


class TestGetManifest:
    def test_contains_all_required_keys(self):
        cfg = NodeConfig(operator="TestCo", api_base="https://tc.example/rcan")
        broadcaster = NodeBroadcaster(cfg)
        manifest = broadcaster.get_manifest()
        assert REQUIRED_MANIFEST_KEYS.issubset(manifest.keys())

    def test_version_field(self):
        broadcaster = NodeBroadcaster(NodeConfig())
        assert broadcaster.get_manifest()["rcan_node_version"] == "1.0"

    def test_sync_endpoint_built_from_api_base(self):
        cfg = NodeConfig(api_base="https://fleet.example")
        broadcaster = NodeBroadcaster(cfg)
        assert broadcaster.get_manifest()["sync_endpoint"] == "https://fleet.example/sync"

    def test_sync_endpoint_empty_when_no_api_base(self):
        broadcaster = NodeBroadcaster(NodeConfig())
        assert broadcaster.get_manifest()["sync_endpoint"] == ""

    def test_capabilities_propagated(self):
        cfg = NodeConfig(capabilities=["resolve", "sync", "attest"])
        broadcaster = NodeBroadcaster(cfg)
        assert broadcaster.get_manifest()["capabilities"] == ["resolve", "sync", "attest"]

    def test_node_type_propagated(self):
        cfg = NodeConfig(node_type="authoritative")
        broadcaster = NodeBroadcaster(cfg)
        assert broadcaster.get_manifest()["node_type"] == "authoritative"

    def test_last_sync_is_iso8601(self):
        import re

        broadcaster = NodeBroadcaster(NodeConfig())
        last_sync = broadcaster.get_manifest()["last_sync"]
        # Basic ISO 8601 UTC check: YYYY-MM-DDTHH:MM:SSZ
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", last_sync)


# ── NodeBroadcaster lifecycle ─────────────────────────────────────────────────


class TestLifecycle:
    def test_start_sets_running(self):
        broadcaster = NodeBroadcaster(NodeConfig())
        broadcaster.start()
        assert broadcaster._running is True

    def test_stop_clears_running(self):
        broadcaster = NodeBroadcaster(NodeConfig())
        broadcaster.start()
        broadcaster.stop()
        assert broadcaster._running is False

    def test_start_mdns_does_not_raise_without_zeroconf(self, monkeypatch):
        """start_mdns() must be safe even when zeroconf / mdns.py is absent."""
        import sys

        monkeypatch.setitem(sys.modules, "castor.rcan.mdns", None)
        broadcaster = NodeBroadcaster(NodeConfig())
        broadcaster.start_mdns()  # should not raise
