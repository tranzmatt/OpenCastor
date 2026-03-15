"""Tests for session expiry zero-velocity motor stop (Protocol 66 §6).

Verifies that _trigger_session_expiry_stop() attempts to write a zero-velocity
command to the motor controller device after marking the session as expired.
"""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import MagicMock, call, mock_open, patch

import pytest

from castor.fs.namespace import Namespace
from castor.fs.permissions import PermissionTable
from castor.fs.safety import SafetyLayer


def _make_safety_layer() -> SafetyLayer:
    """Create a minimal SafetyLayer for testing."""
    ns = Namespace()
    ns.mkdir("/var/log")
    ns.mkdir("/proc")
    ns.write("/proc/status", "active")
    perms = PermissionTable()
    return SafetyLayer(ns, perms)


def test_session_expiry_sets_expired_stops():
    """After _trigger_session_expiry_stop, the principal should be in _session_expired_stops."""
    sl = _make_safety_layer()
    sl._trigger_session_expiry_stop("test_principal")
    assert "test_principal" in sl._session_expired_stops


def test_session_expiry_writes_zero_velocity_when_motor_exists():
    """When /dev/motor exists, zero-velocity JSON should be written to it."""
    sl = _make_safety_layer()

    m = mock_open()
    with patch("os.path.exists", return_value=True), patch("builtins.open", m):
        sl._trigger_session_expiry_stop("test_principal")

    # open() should have been called with /dev/motor
    open_calls = [c for c in m.call_args_list if "/dev/motor" in str(c)]
    assert len(open_calls) >= 1, "Expected open('/dev/motor', ...) call"

    # The written payload should be valid JSON with velocity=0.0
    written = "".join(call.args[0] for call in m().write.call_args_list)
    payload = json.loads(written)
    assert payload["velocity"] == 0.0
    assert payload["angular"] == 0.0
    assert payload["source"] == "session_expiry_stop"


def test_session_expiry_skips_write_when_no_motor():
    """When /dev/motor does not exist, no write attempt should be made."""
    sl = _make_safety_layer()

    m = mock_open()
    with patch("os.path.exists", return_value=False), patch("builtins.open", m):
        sl._trigger_session_expiry_stop("test_principal")

    # No /dev/motor write expected
    motor_calls = [c for c in m.call_args_list if "/dev/motor" in str(c)]
    assert len(motor_calls) == 0


def test_session_expiry_swallows_write_exception():
    """A failed motor write should not propagate — session expiry must still complete."""
    sl = _make_safety_layer()

    with patch("os.path.exists", return_value=True), patch(
        "builtins.open", side_effect=OSError("device busy")
    ):
        # Should not raise
        sl._trigger_session_expiry_stop("test_principal")

    assert "test_principal" in sl._session_expired_stops


def test_session_expiry_audit_logged():
    """Session expiry stop should write an audit entry to /var/log/safety."""
    sl = _make_safety_layer()

    with patch("os.path.exists", return_value=False):
        sl._trigger_session_expiry_stop("test_principal")

    safety_log = sl.ns.read("/var/log/safety") or []
    events = [e.get("event") for e in safety_log]
    assert "session_expiry_stop" in events
