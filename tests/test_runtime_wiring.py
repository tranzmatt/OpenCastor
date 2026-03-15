"""Tests for SensorMonitor → SafetyLayer wiring (Protocol 66).

Verifies that wire_safety_layer() correctly connects a SensorMonitor to a
SafetyLayer so that consecutive critical sensor events trigger an e-stop.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from castor.safety.monitor import (
    MonitorSnapshot,
    SensorMonitor,
    SensorReading,
    wire_safety_layer,
)


def _make_critical_snapshot() -> MonitorSnapshot:
    """Build a snapshot with overall_status=critical."""
    snap = MonitorSnapshot(timestamp=1.0)
    snap.cpu_temp_c = 90.0
    snap.overall_status = "critical"
    snap.readings = [
        SensorReading(name="cpu_temp", value=90.0, unit="°C", status="critical"),
    ]
    return snap


def _make_safety_mock() -> MagicMock:
    """Build a safety layer mock with a permissions sub-mock."""
    safety_layer = MagicMock()
    safety_layer.perms = MagicMock()
    return safety_layer


def test_wire_safety_layer_calls_estop_on_critical():
    """wire_safety_layer should connect monitor so that after N consecutive
    critical readings, safety_layer.estop() is invoked."""
    monitor = SensorMonitor(consecutive_critical=2)
    safety_layer = _make_safety_mock()

    wire_safety_layer(monitor, safety_layer)

    snap = _make_critical_snapshot()
    # Trigger critical callbacks (which capture the snapshot)
    for cb in monitor._critical_callbacks:
        cb(snap)

    # Fire the estop callback directly
    assert monitor._estop_callback is not None, "estop callback should be set"
    monitor._estop_callback()

    safety_layer.estop.assert_called_once()
    call_kwargs = safety_layer.estop.call_args
    assert call_kwargs is not None
    # principal="monitor" must be passed
    principal = call_kwargs.kwargs.get("principal") or (
        call_kwargs.args[0] if call_kwargs.args else None
    )
    assert principal == "monitor"


def test_wire_safety_layer_grants_estop_cap():
    """wire_safety_layer should attempt to grant CAP_ESTOP to 'monitor' principal."""
    from castor.fs.permissions import Cap

    monitor = SensorMonitor()
    safety_layer = _make_safety_mock()

    wire_safety_layer(monitor, safety_layer)

    safety_layer.perms.grant_cap.assert_called_once_with("monitor", Cap.ESTOP)


def test_wire_safety_layer_registers_critical_callback():
    """After wiring, monitor should have at least one critical callback."""
    monitor = SensorMonitor()
    safety_layer = _make_safety_mock()

    wire_safety_layer(monitor, safety_layer)

    assert len(monitor._critical_callbacks) >= 1


def test_wire_safety_layer_estop_reason_includes_readings():
    """The estop reason string should contain sensor reading details."""
    monitor = SensorMonitor(consecutive_critical=1)
    safety_layer = _make_safety_mock()

    wire_safety_layer(monitor, safety_layer)

    snap = _make_critical_snapshot()
    for cb in monitor._critical_callbacks:
        cb(snap)

    monitor._estop_callback()

    safety_layer.estop.assert_called_once()
    reason_arg = safety_layer.estop.call_args.kwargs.get("reason", "")
    assert "SensorMonitor" in reason_arg or "sensor" in reason_arg.lower()


def test_initialize_safety_returns_monitor():
    """castor.initialize_safety() should return a wired SensorMonitor."""
    safety_layer = _make_safety_mock()

    import castor

    monitor = castor.initialize_safety(safety_layer, config={"monitor": {"interval": 10.0}})

    assert isinstance(monitor, SensorMonitor)
    assert monitor.interval == 10.0
    assert monitor._estop_callback is not None
