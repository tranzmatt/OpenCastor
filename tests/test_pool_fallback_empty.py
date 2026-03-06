"""Tests for ProviderPool fallback_on_empty_response (Issue #399)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from castor.providers.base import Thought
from castor.providers.pool_provider import ProviderPool


def _make_pool(cfg_extra=None):
    """Build a ProviderPool with two mocked providers."""
    cfg = {
        "pool_strategy": "round_robin",
        "pool_fallback": True,
        "pool": [{"provider": "mock1"}, {"provider": "mock2"}],
    }
    if cfg_extra:
        cfg.update(cfg_extra)
    p1 = MagicMock()
    p1.model_name = "mock1"
    p2 = MagicMock()
    p2.model_name = "mock2"
    with patch("castor.providers.get_provider", side_effect=[p1, p2]):
        pool = ProviderPool(cfg)
    return pool, p1, p2


def _make_single_pool(cfg_extra=None):
    """Build a ProviderPool with a single mocked provider and no fallback."""
    cfg = {
        "pool_strategy": "round_robin",
        "pool_fallback": False,
        "pool": [{"provider": "mock1"}],
    }
    if cfg_extra:
        cfg.update(cfg_extra)
    p1 = MagicMock()
    p1.model_name = "mock1"
    with patch("castor.providers.get_provider", side_effect=[p1]):
        pool = ProviderPool(cfg)
    return pool, p1


# ------------------------------------------------------------------
# Feature flag defaults
# ------------------------------------------------------------------


def test_fallback_on_empty_defaults_to_false():
    """pool_fallback_on_empty should be False by default."""
    pool, _, _ = _make_pool()
    assert pool._fallback_on_empty is False


def test_fallback_on_empty_true_when_configured():
    """pool_fallback_on_empty=True should set the flag to True."""
    pool, _, _ = _make_pool({"pool_fallback_on_empty": True})
    assert pool._fallback_on_empty is True


# ------------------------------------------------------------------
# Fallback path (pool_fallback=True, two providers)
# ------------------------------------------------------------------


def test_empty_response_falls_through_to_next_provider():
    """When pool_fallback_on_empty=True, an empty raw_text should cause retry."""
    pool, p1, p2 = _make_pool({"pool_fallback_on_empty": True})
    p1.think.return_value = Thought(raw_text="", action={"type": "stop"})
    p2.think.return_value = Thought(raw_text="go forward", action={"type": "move"})

    result = pool.think(b"", "move forward")

    assert result.raw_text == "go forward"
    assert p1.think.call_count == 1
    assert p2.think.call_count == 1


def test_empty_response_returned_when_flag_disabled():
    """When pool_fallback_on_empty=False, an empty raw_text should be returned as-is."""
    pool, p1, p2 = _make_pool({"pool_fallback_on_empty": False})
    p1.think.return_value = Thought(raw_text="", action={"type": "stop"})
    p2.think.return_value = Thought(raw_text="go forward", action={"type": "move"})

    result = pool.think(b"", "move forward")

    assert result.raw_text == ""
    # p2 should not have been called since p1 succeeded and flag is off
    assert p2.think.call_count == 0


def test_non_empty_response_returned_regardless_of_flag():
    """A non-empty response should always be returned, flag has no effect."""
    pool, p1, p2 = _make_pool({"pool_fallback_on_empty": True})
    p1.think.return_value = Thought(raw_text="move left", action={"type": "move"})
    p2.think.return_value = Thought(raw_text="other", action={"type": "stop"})

    result = pool.think(b"", "turn left")

    assert result.raw_text == "move left"
    assert p2.think.call_count == 0


def test_whitespace_only_response_treated_as_empty_when_enabled():
    """A whitespace-only raw_text should trigger fallback when flag is True."""
    pool, p1, p2 = _make_pool({"pool_fallback_on_empty": True})
    p1.think.return_value = Thought(raw_text="   \t\n  ", action={"type": "stop"})
    p2.think.return_value = Thought(raw_text="all clear", action={"type": "move"})

    result = pool.think(b"", "scan area")

    assert result.raw_text == "all clear"
    assert p2.think.call_count == 1


def test_none_raw_text_treated_as_empty_when_enabled():
    """None raw_text should trigger fallback when flag is True."""
    pool, p1, p2 = _make_pool({"pool_fallback_on_empty": True})
    p1.think.return_value = Thought(raw_text=None, action={"type": "stop"})
    p2.think.return_value = Thought(raw_text="valid response", action={"type": "move"})

    result = pool.think(b"", "do something")

    assert result.raw_text == "valid response"
    assert p2.think.call_count == 1


def test_whitespace_response_returned_when_flag_disabled():
    """Whitespace-only response should be returned as-is when flag is False."""
    pool, p1, p2 = _make_pool({"pool_fallback_on_empty": False})
    p1.think.return_value = Thought(raw_text="   ", action={"type": "stop"})
    p2.think.return_value = Thought(raw_text="other", action={"type": "move"})

    result = pool.think(b"", "do something")

    assert result.raw_text == "   "
    assert p2.think.call_count == 0


# ------------------------------------------------------------------
# Non-fallback path (pool_fallback=False, single provider)
# ------------------------------------------------------------------


def test_single_provider_empty_raises_runtimeerror():
    """With no fallback and pool_fallback_on_empty=True, empty response should raise."""
    pool, p1 = _make_single_pool({"pool_fallback_on_empty": True})
    p1.think.return_value = Thought(raw_text="", action={"type": "stop"})

    with pytest.raises(RuntimeError, match="empty response"):
        pool.think(b"", "do something")


def test_single_provider_none_raw_text_raises_runtimeerror():
    """With no fallback and pool_fallback_on_empty=True, None raw_text should raise."""
    pool, p1 = _make_single_pool({"pool_fallback_on_empty": True})
    p1.think.return_value = Thought(raw_text=None, action={"type": "stop"})

    with pytest.raises(RuntimeError, match="empty response"):
        pool.think(b"", "do something")


def test_single_provider_whitespace_raises_runtimeerror():
    """With no fallback and pool_fallback_on_empty=True, whitespace-only should raise."""
    pool, p1 = _make_single_pool({"pool_fallback_on_empty": True})
    p1.think.return_value = Thought(raw_text="\n\t ", action={"type": "stop"})

    with pytest.raises(RuntimeError, match="empty response"):
        pool.think(b"", "do something")


def test_single_provider_no_error_when_flag_disabled():
    """With no fallback and pool_fallback_on_empty=False, empty response is returned."""
    pool, p1 = _make_single_pool({"pool_fallback_on_empty": False})
    p1.think.return_value = Thought(raw_text="", action={"type": "stop"})

    result = pool.think(b"", "do something")
    assert result.raw_text == ""


def test_all_providers_empty_raises_runtimeerror():
    """When all providers return empty and fallback_on_empty=True, a RuntimeError is raised."""
    pool, p1, p2 = _make_pool({"pool_fallback_on_empty": True})
    p1.think.return_value = Thought(raw_text="", action={"type": "stop"})
    p2.think.return_value = Thought(raw_text="", action={"type": "stop"})

    with pytest.raises(RuntimeError):
        pool.think(b"", "do something")
