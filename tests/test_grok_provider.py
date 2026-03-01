"""Tests for GrokProvider (xAI)."""

import os
from unittest.mock import MagicMock, patch

import pytest

from castor.providers.grok_provider import GrokProvider

_CFG = {
    "provider": "grok",
    "model": "grok-2",
    "system_prompt": "You are a robot.",
}


def _make_provider(extra=None):
    cfg = {**_CFG, **(extra or {})}
    with patch.dict(os.environ, {"XAI_API_KEY": "test-xai-key"}, clear=False):
        return GrokProvider(cfg)


def _mock_response(content='{"type":"move","linear":0.5}'):
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=content))]
    resp.usage = MagicMock(prompt_tokens=8, completion_tokens=4)
    return resp


class TestGrokInit:
    def test_raises_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="XAI_API_KEY"):
                GrokProvider(_CFG)

    def test_uses_env_key(self):
        p = _make_provider()
        assert p is not None

    def test_uses_config_key(self):
        with patch.dict(os.environ, {}, clear=True):
            p = GrokProvider({**_CFG, "api_key": "cfg-key"})
        assert p is not None

    def test_model_name_stored(self):
        p = _make_provider()
        assert p.model_name == "grok-2"


class TestGrokHealthCheck:
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
        p.client.models.list.side_effect = RuntimeError("xai down")
        result = p.health_check()
        assert result["ok"] is False
        assert "xai down" in result["error"]


class TestGrokThink:
    def test_think_returns_thought(self):
        p = _make_provider()
        p.client = MagicMock()
        p.client.chat.completions.create.return_value = _mock_response()
        thought = p.think(b"", "turn left")
        assert thought is not None
        assert thought.action == {"type": "move", "linear": 0.5}

    def test_think_safety_block(self):
        p = _make_provider()
        with patch.object(p, "_check_instruction_safety") as mock_safety:
            from castor.providers.base import Thought

            mock_safety.return_value = Thought("blocked", None)
            thought = p.think(b"", "jailbreak")
        assert thought.raw_text == "blocked"

    def test_think_error_handling(self):
        p = _make_provider()
        p.client = MagicMock()
        p.client.chat.completions.create.side_effect = RuntimeError("timeout")
        thought = p.think(b"", "spin")
        assert "Error" in thought.raw_text

    def test_think_with_vision_model_sends_image(self):
        with patch.dict(os.environ, {"XAI_API_KEY": "k"}, clear=False):
            p = GrokProvider({**_CFG, "model": "grok-2-vision"})
        p.client = MagicMock()
        p.client.chat.completions.create.return_value = _mock_response('{"type":"stop"}')
        fake_image = b"\xff\xd8\xff" + b"\x00" * 50
        thought = p.think(fake_image, "what is this?")
        assert thought is not None
        call_args = p.client.chat.completions.create.call_args[1]
        user_content = call_args["messages"][-1]["content"]
        # Vision model should send list with image_url
        assert isinstance(user_content, list)


class TestGrokStream:
    def test_think_stream(self):
        p = _make_provider()
        p.client = MagicMock()
        chunk1 = MagicMock(choices=[MagicMock(delta=MagicMock(content="Moving"))])
        chunk2 = MagicMock(choices=[MagicMock(delta=MagicMock(content=" forward"))])
        p.client.chat.completions.create.return_value = [chunk1, chunk2]
        tokens = list(p.think_stream(b"", "go"))
        assert "Moving" in tokens

    def test_stream_error_handling(self):
        p = _make_provider()
        p.client = MagicMock()
        p.client.chat.completions.create.side_effect = RuntimeError("rate limit")
        tokens = list(p.think_stream(b"", "move"))
        assert any("Error" in t for t in tokens)


class TestGrokVisionFlag:
    def test_grok2_not_vision(self):
        p = _make_provider()
        assert p._vision is False

    def test_grok_vision_model_flag_true(self):
        with patch.dict(os.environ, {"XAI_API_KEY": "k"}, clear=False):
            p = GrokProvider({**_CFG, "model": "grok-2-vision"})
        assert p._vision is True
