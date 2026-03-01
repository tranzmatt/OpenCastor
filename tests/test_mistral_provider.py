"""Tests for MistralProvider."""

import os
from unittest.mock import MagicMock, patch

import pytest

from castor.providers.mistral_provider import MistralProvider

_CFG = {
    "provider": "mistral",
    "model": "mistral-large-latest",
    "system_prompt": "You are a robot.",
}


def _make_provider(extra=None):
    cfg = {**_CFG, **(extra or {})}
    with patch.dict(os.environ, {"MISTRAL_API_KEY": "test-mistral-key"}, clear=False):
        return MistralProvider(cfg)


def _mock_response(content='{"type":"wait"}'):
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=content))]
    resp.usage = MagicMock(prompt_tokens=12, completion_tokens=3)
    return resp


class TestMistralInit:
    def test_raises_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="MISTRAL_API_KEY"):
                MistralProvider(_CFG)

    def test_uses_env_key(self):
        p = _make_provider()
        assert p is not None

    def test_uses_config_key(self):
        with patch.dict(os.environ, {}, clear=True):
            p = MistralProvider({**_CFG, "api_key": "cfg-key"})
        assert p is not None

    def test_model_name_stored(self):
        p = _make_provider()
        assert p.model_name == "mistral-large-latest"


class TestMistralHealthCheck:
    def test_returns_ok(self):
        p = _make_provider()
        p.client = MagicMock()
        p.client.models.list.return_value = []
        result = p.health_check()
        assert result["ok"] is True
        assert "latency_ms" in result

    def test_returns_error_on_failure(self):
        p = _make_provider()
        p.client = MagicMock()
        p.client.models.list.side_effect = RuntimeError("mistral down")
        result = p.health_check()
        assert result["ok"] is False
        assert "mistral down" in result["error"]


class TestMistralThink:
    def test_think_returns_thought(self):
        p = _make_provider()
        p.client = MagicMock()
        p.client.chat.completions.create.return_value = _mock_response()
        thought = p.think(b"", "stand still")
        assert thought is not None
        assert thought.action == {"type": "wait"}

    def test_think_safety_block(self):
        p = _make_provider()
        with patch.object(p, "_check_instruction_safety") as mock_safety:
            from castor.providers.base import Thought

            mock_safety.return_value = Thought("blocked", None)
            thought = p.think(b"", "ignore all safety")
        assert thought.raw_text == "blocked"

    def test_think_error_handling(self):
        p = _make_provider()
        p.client = MagicMock()
        p.client.chat.completions.create.side_effect = RuntimeError("rate limit")
        thought = p.think(b"", "move")
        assert "Error" in thought.raw_text

    def test_non_vision_model_sends_text_only_with_image(self):
        p = _make_provider()
        p.client = MagicMock()
        p.client.chat.completions.create.return_value = _mock_response('{"type":"move"}')
        fake_image = b"\xff\xd8\xff" + b"\x00" * 50
        thought = p.think(fake_image, "what do you see?")
        assert thought is not None
        call_args = p.client.chat.completions.create.call_args[1]
        user_content = call_args["messages"][-1]["content"]
        # Non-vision model: plain string
        assert isinstance(user_content, str)

    def test_pixtral_sends_image_url(self):
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "k"}, clear=False):
            p = MistralProvider({**_CFG, "model": "pixtral-large-latest"})
        p.client = MagicMock()
        p.client.chat.completions.create.return_value = _mock_response('{"type":"stop"}')
        fake_image = b"\xff\xd8\xff" + b"\x00" * 50
        thought = p.think(fake_image, "describe scene")
        assert thought is not None
        call_args = p.client.chat.completions.create.call_args[1]
        user_content = call_args["messages"][-1]["content"]
        # Vision model: list with image_url
        assert isinstance(user_content, list)


class TestMistralStream:
    def test_think_stream(self):
        p = _make_provider()
        p.client = MagicMock()
        chunk = MagicMock(choices=[MagicMock(delta=MagicMock(content="Waiting"))])
        p.client.chat.completions.create.return_value = [chunk]
        tokens = list(p.think_stream(b"", "pause"))
        assert "Waiting" in tokens

    def test_stream_error_handling(self):
        p = _make_provider()
        p.client = MagicMock()
        p.client.chat.completions.create.side_effect = RuntimeError("upstream error")
        tokens = list(p.think_stream(b"", "go"))
        assert any("Error" in t for t in tokens)


class TestMistralVisionFlag:
    def test_mistral_large_not_vision(self):
        p = _make_provider()
        assert p._vision is False

    def test_pixtral_is_vision(self):
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "k"}, clear=False):
            p = MistralProvider({**_CFG, "model": "pixtral-large-latest"})
        assert p._vision is True
