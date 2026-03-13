"""Tests for RCAN §21 Registry Framework (REGISTRY_REGISTER / REGISTRY_RESOLVE)."""

import pytest

from castor.rcan.message import MessageType
from castor.rcan.registry import (
    RegistryMessage,
    RegistryResolveRequest,
    RegistryResolveResponse,
)


class TestRegistryMessageType:
    def test_registry_register_value(self):
        assert MessageType.REGISTRY_REGISTER == 13

    def test_registry_resolve_value(self):
        assert MessageType.REGISTRY_RESOLVE == 14

    def test_registry_register_name_lookup(self):
        assert MessageType["REGISTRY_REGISTER"] is MessageType.REGISTRY_REGISTER

    def test_registry_resolve_name_lookup(self):
        assert MessageType["REGISTRY_RESOLVE"] is MessageType.REGISTRY_RESOLVE


class TestRegistryMessageRoundTrip:
    def test_to_message_type(self):
        msg = RegistryMessage(
            msg_id="m-001",
            rrn="rrn://example.org/robots/rover-1",
            ruri="rcan://192.168.1.10:8000/rover-1",
            public_key="-----BEGIN PUBLIC KEY-----\nMFYw...\n-----END PUBLIC KEY-----",
        )
        raw = msg.to_message()
        assert raw["type"] == MessageType.REGISTRY_REGISTER

    def test_to_message_payload_fields(self):
        msg = RegistryMessage(
            msg_id="m-002",
            rrn="rrn://example.org/robots/arm-1",
            ruri="rcan://arm.local:8000/arm-1",
            public_key="pk-placeholder",
            timestamp=1700000000.0,
        )
        raw = msg.to_message()
        payload = raw["payload"]
        assert payload["rrn"] == "rrn://example.org/robots/arm-1"
        assert payload["ruri"] == "rcan://arm.local:8000/arm-1"
        assert payload["public_key"] == "pk-placeholder"
        assert payload["timestamp"] == 1700000000.0

    def test_from_message_round_trip(self):
        original = RegistryMessage(
            msg_id="m-003",
            rrn="rrn://example.org/robots/rover-2",
            ruri="rcan://rover2.local:8000/rover-2",
            public_key="pk-data",
            timestamp=1700001234.5,
        )
        raw = original.to_message()
        restored = RegistryMessage.from_message(raw)
        assert restored.rrn == original.rrn
        assert restored.ruri == original.ruri
        assert restored.public_key == original.public_key
        assert restored.timestamp == original.timestamp

    def test_from_message_msg_id_preserved(self):
        original = RegistryMessage(
            msg_id="m-004",
            rrn="rrn://x/y",
            ruri="rcan://x:8000/y",
            public_key="pk",
        )
        raw = original.to_message()
        restored = RegistryMessage.from_message(raw)
        assert restored.msg_id == "m-004"


class TestRegistryMessageMissingFields:
    def test_missing_rrn_raises(self):
        with pytest.raises(ValueError, match="rrn"):
            RegistryMessage.from_message(
                {"msg_id": "x", "payload": {"ruri": "rcan://x", "public_key": "pk"}}
            )

    def test_missing_ruri_raises(self):
        with pytest.raises(ValueError, match="ruri"):
            RegistryMessage.from_message(
                {
                    "msg_id": "x",
                    "payload": {
                        "rrn": "rrn://x/y",
                        "public_key": "pk",
                    },
                }
            )

    def test_missing_public_key_raises(self):
        with pytest.raises(ValueError, match="public_key"):
            RegistryMessage.from_message(
                {
                    "msg_id": "x",
                    "payload": {"rrn": "rrn://x/y", "ruri": "rcan://x"},
                }
            )


class TestRegistryResolveRequest:
    def test_to_message_type(self):
        req = RegistryResolveRequest(rrn="rrn://example.org/robots/rover-1")
        raw = req.to_message()
        assert raw["type"] == MessageType.REGISTRY_RESOLVE

    def test_to_message_rrn_in_payload(self):
        req = RegistryResolveRequest(rrn="rrn://example.org/robots/arm-2", msg_id="req-001")
        raw = req.to_message()
        assert raw["payload"]["rrn"] == "rrn://example.org/robots/arm-2"
        assert raw["msg_id"] == "req-001"

    def test_auto_generated_msg_id(self):
        req1 = RegistryResolveRequest(rrn="rrn://x/y")
        req2 = RegistryResolveRequest(rrn="rrn://x/y")
        assert req1.msg_id != req2.msg_id


class TestRegistryResolveResponse:
    def test_to_message_type(self):
        resp = RegistryResolveResponse(
            rrn="rrn://example.org/robots/rover-1",
            ruri="rcan://rover1.local:8000/rover-1",
            verified=True,
            tier="pro",
        )
        raw = resp.to_message()
        assert raw["type"] == MessageType.REGISTRY_RESOLVE

    def test_to_message_all_fields(self):
        resp = RegistryResolveResponse(
            rrn="rrn://example.org/robots/arm-1",
            ruri="rcan://arm1.local:8000/arm-1",
            verified=False,
            tier="free",
        )
        raw = resp.to_message()
        payload = raw["payload"]
        assert payload["rrn"] == "rrn://example.org/robots/arm-1"
        assert payload["ruri"] == "rcan://arm1.local:8000/arm-1"
        assert payload["verified"] is False
        assert payload["tier"] == "free"
