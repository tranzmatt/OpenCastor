"""Tests for ActionValidator with custom schema (#392)."""

from castor.action_validator import ActionValidator, init_from_config, validate_action

# ── basic instantiation ───────────────────────────────────────────────────────


def test_action_validator_instantiates():
    av = ActionValidator()
    assert av is not None


def test_action_validator_with_no_custom_schemas():
    av = ActionValidator()
    assert len(av.known_types()) > 0


def test_action_validator_known_types_includes_move():
    av = ActionValidator()
    assert "move" in av.known_types()


def test_action_validator_known_types_includes_stop():
    av = ActionValidator()
    assert "stop" in av.known_types()


# ── built-in validation ───────────────────────────────────────────────────────


def test_validate_stop_action():
    av = ActionValidator()
    result = av.validate({"type": "stop"})
    assert result.valid is True


def test_validate_move_action():
    av = ActionValidator()
    result = av.validate({"type": "move", "linear": 0.5, "angular": 0.0})
    assert result.valid is True


def test_validate_unknown_type_returns_result():
    av = ActionValidator()
    result = av.validate({"type": "nonexistent_xyz"})
    assert result is not None


# ── custom schema registration ────────────────────────────────────────────────


def test_custom_schema_registered():
    av = ActionValidator(custom_schemas={"spray": {"type": "object", "required": ["type"]}})
    assert "spray" in av.known_types()


def test_custom_schema_source_is_rcan_config():
    av = ActionValidator(custom_schemas={"spray": {"type": "object", "required": ["type"]}})
    source = av.schema_source_for("spray")
    assert source == "rcan_config"


def test_builtin_schema_source_is_builtin():
    av = ActionValidator()
    source = av.schema_source_for("move")
    assert source == "builtin"


def test_custom_schema_validates_matching_action():
    schema = {
        "type": "object",
        "required": ["type", "channel"],
        "properties": {
            "type": {"type": "string"},
            "channel": {"type": "integer", "minimum": 0, "maximum": 15},
        },
    }
    av = ActionValidator(custom_schemas={"servo": schema})
    result = av.validate({"type": "servo", "channel": 3})
    assert result is not None


def test_custom_schema_rejects_missing_required_field():
    schema = {
        "type": "object",
        "required": ["type", "power_w"],
        "properties": {
            "type": {"type": "string"},
            "power_w": {"type": "number"},
        },
    }
    av = ActionValidator(custom_schemas={"laser": schema})
    result = av.validate({"type": "laser"})  # missing power_w
    # Should fail validation
    assert result.valid is False


# ── init_from_config ──────────────────────────────────────────────────


def test_init_from_config_with_empty_config():
    av = init_from_config({})
    assert isinstance(av, ActionValidator)


def test_init_from_config_with_schemas():
    config = {
        "action_schemas": {
            "custom_turn": {
                "type": "object",
                "required": ["type"],
            }
        }
    }
    av = init_from_config(config)
    assert "custom_turn" in av.known_types()


def test_init_from_config_source_is_rcan():
    config = {"action_schemas": {"my_action": {"type": "object", "required": ["type"]}}}
    av = init_from_config(config)
    assert av.schema_source_for("my_action") == "rcan_config"


# ── validate_action convenience function ─────────────────────────────────────


def test_validate_action_function_works():
    result = validate_action({"type": "stop"})
    assert result is not None


def test_validate_action_unknown_type():
    result = validate_action({"type": "xyz_unknown"})
    assert result is not None  # should not raise
