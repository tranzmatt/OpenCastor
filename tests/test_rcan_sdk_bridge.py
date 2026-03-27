"""Tests for castor.rcan.sdk_bridge — rcan-py SDK interoperability."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# URI conversion
# ---------------------------------------------------------------------------


def test_ruri_to_robot_uri_basic():
    from castor.rcan.ruri import RURI
    from castor.rcan.sdk_bridge import ruri_to_robot_uri

    ruri = RURI(manufacturer="acme", model="arm", instance="abc12345")
    robot_uri = ruri_to_robot_uri(ruri)
    assert robot_uri.manufacturer == "acme"
    assert robot_uri.model == "arm"
    assert robot_uri.device_id == "abc12345"
    assert str(robot_uri).startswith("rcan://")


def test_ruri_to_robot_uri_with_config():
    from castor.rcan.ruri import RURI
    from castor.rcan.sdk_bridge import ruri_to_robot_uri

    ruri = RURI(manufacturer="continuonai", model="continuonbot", instance="pi5lab01")
    config = {"metadata": {"version": "v2", "registry": "registry.rcan.dev"}}
    robot_uri = ruri_to_robot_uri(ruri, config)
    assert robot_uri.version == "v2"
    assert robot_uri.registry == "registry.rcan.dev"


def test_ruri_to_robot_uri_from_spec_string():
    from castor.rcan.sdk_bridge import ruri_to_robot_uri

    uri_str = "rcan://registry.rcan.dev/acme/arm/v2/unit-001"
    robot_uri = ruri_to_robot_uri(uri_str)
    assert robot_uri.manufacturer == "acme"
    assert robot_uri.version == "v2"


def test_robot_uri_to_ruri():
    from rcan import RobotURI

    from castor.rcan.sdk_bridge import robot_uri_to_ruri

    robot_uri = RobotURI.parse("rcan://registry.rcan.dev/acme/arm/v2/unit-001")
    ruri = robot_uri_to_ruri(robot_uri)
    assert ruri.manufacturer == "acme"
    assert ruri.model == "arm"
    assert ruri.instance == "unit-001"


def test_roundtrip_uri():
    from castor.rcan.ruri import RURI
    from castor.rcan.sdk_bridge import robot_uri_to_ruri, ruri_to_robot_uri

    original = RURI(manufacturer="acme", model="bot", instance="abc12345")
    robot_uri = ruri_to_robot_uri(original)
    restored = robot_uri_to_ruri(robot_uri)
    assert restored.manufacturer == original.manufacturer
    assert restored.model == original.model
    assert restored.instance == original.instance


# ---------------------------------------------------------------------------
# Message parsing
# ---------------------------------------------------------------------------


def test_parse_inbound_spec_format():
    from rcan import RCANMessage

    from castor.rcan.sdk_bridge import parse_inbound

    body = {
        "rcan": "2.2",
        "cmd": "move_forward",
        "target": "rcan://registry.rcan.dev/acme/arm/v2/unit-001",
        "params": {"distance_m": 1.0},
        "confidence": 0.9,
    }
    result = parse_inbound(body)
    assert isinstance(result, RCANMessage)
    assert result.cmd == "move_forward"
    assert result.confidence == 0.9


def test_parse_inbound_opencastor_format():
    from castor.rcan.message import RCANMessage as OCMessage
    from castor.rcan.sdk_bridge import parse_inbound

    body = {
        "type": 3,  # COMMAND
        "source": "rcan://acme.arm.abc12345",
        "target": "rcan://acme.arm.abc12345",
        "payload": {"cmd": "stop"},
    }
    result = parse_inbound(body)
    assert isinstance(result, OCMessage)


def test_spec_message_to_opencastor():
    from rcan import RCANMessage

    from castor.rcan.message import MessageType
    from castor.rcan.sdk_bridge import spec_message_to_opencastor

    spec_msg = RCANMessage(
        cmd="stop",
        target="rcan://registry.rcan.dev/acme/arm/v2/unit-001",
        params={"reason": "emergency"},
        confidence=0.99,
        sender="operator-alice",
    )
    oc_msg = spec_message_to_opencastor(spec_msg)
    assert oc_msg.type == MessageType.COMMAND
    assert oc_msg.payload["cmd"] == "stop"
    assert oc_msg.payload["confidence"] == 0.99
    assert oc_msg.source == "operator-alice"
    assert oc_msg.id == spec_msg.msg_id


# ---------------------------------------------------------------------------
# CommitmentRecord generation
# ---------------------------------------------------------------------------


def test_action_to_commitment_record():
    from rcan import CommitmentRecord

    from castor.rcan.sdk_bridge import action_to_commitment_record

    record = action_to_commitment_record(
        action_type="move_forward",
        params={"distance_m": 1.0},
        robot_uri_str="rcan://registry.rcan.dev/acme/arm/v2/unit-001",
        confidence=0.91,
        model_identity="Qwen2.5-7B",
        safety_approved=True,
    )
    assert isinstance(record, CommitmentRecord)
    assert record.action == "move_forward"
    assert record.confidence == 0.91
    assert record.safety_approved is True


def test_commitment_record_seal_and_verify():
    from castor.rcan.sdk_bridge import action_to_commitment_record

    record = action_to_commitment_record(
        action_type="stop",
        params={},
        robot_uri_str="rcan://registry.rcan.dev/acme/arm/v2/unit-001",
        safety_approved=True,
    )
    record.seal("test-secret")
    assert record.verify("test-secret") is True
    assert record.verify("wrong-secret") is False


def test_audit_entry_to_commitment_record():
    from castor.rcan.sdk_bridge import audit_entry_to_commitment_record

    entry = {
        "ts": 1234567890.0,
        "event": "motor_command",
        "action": {"cmd": "forward", "speed": 0.5},
        "source": "rcan://acme.arm.abc",
        "safety_approved": True,
    }
    record = audit_entry_to_commitment_record(entry)
    assert record.action == "motor_command"
    assert record.safety_approved is True


# ---------------------------------------------------------------------------
# Gate bridging
# ---------------------------------------------------------------------------


def test_opencastor_gate_to_rcan():
    from rcan import ConfidenceGate

    from castor.confidence_gate import ConfidenceGate as OCGate
    from castor.rcan.sdk_bridge import opencastor_gate_to_rcan

    oc_gate = OCGate(scope="control", min_confidence=0.75, on_fail="block")
    rcan_gate = opencastor_gate_to_rcan(oc_gate)
    assert isinstance(rcan_gate, ConfidenceGate)
    assert rcan_gate.threshold == 0.75


def test_rcan_gate_to_opencastor():
    from rcan import ConfidenceGate

    from castor.rcan.sdk_bridge import rcan_gate_to_opencastor

    rcan_gate = ConfidenceGate(threshold=0.8)
    oc_gate = rcan_gate_to_opencastor(rcan_gate, scope="nav", on_fail="escalate")
    assert oc_gate.min_confidence == 0.8
    assert oc_gate.scope == "nav"
    assert oc_gate.on_fail == "escalate"


def test_gate_roundtrip():
    from castor.confidence_gate import ConfidenceGate as OCGate
    from castor.rcan.sdk_bridge import opencastor_gate_to_rcan, rcan_gate_to_opencastor

    original = OCGate(scope="nav", min_confidence=0.65, on_fail="escalate")
    rcan_gate = opencastor_gate_to_rcan(original)
    restored = rcan_gate_to_opencastor(rcan_gate, scope="nav", on_fail="escalate")
    assert abs(restored.min_confidence - original.min_confidence) < 0.001


# ---------------------------------------------------------------------------
# Compliance check
# ---------------------------------------------------------------------------


def test_check_compliance_minimal_config():
    from castor.rcan.sdk_bridge import check_compliance

    config = {}
    issues = check_compliance(config)
    # Should flag missing manufacturer and model at minimum
    assert any("manufacturer" in i for i in issues)
    assert any("model" in i for i in issues)


def test_check_compliance_full_config():
    from castor.rcan.sdk_bridge import check_compliance

    config = {
        "rcan_version": "1.2",
        "metadata": {
            "manufacturer": "acme",
            "model": "arm",
        },
        "rcan_protocol": {
            "version": "1.2",
            "jwt_auth": {"enabled": True},
        },
        "agent": {
            "confidence_gates": [{"scope": "control", "min_confidence": 0.7}],
            "hitl_gates": [{"action_types": ["grip"], "require_auth": True}],
        },
    }
    issues = check_compliance(config)
    assert issues == [], f"Expected no issues, got: {issues}"
