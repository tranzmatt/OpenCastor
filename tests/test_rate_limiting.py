"""Tests for castor.rate_limiting — sliding-window token bucket (issue #486)."""

import pytest
from fastapi import HTTPException

from castor.rate_limiting import (
    EndpointLimit,
    RateLimitConfig,
    RateLimiter,
    get_limiter,
    init_limiter,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def make_limiter(
    endpoint: str = "/api/command", per_ip: int = 5, window_s: float = 60.0
) -> RateLimiter:
    config = RateLimitConfig(
        limits=[EndpointLimit(endpoint=endpoint, per_ip=per_ip, per_user=0, window_s=window_s)]
    )
    return RateLimiter(config)


# ── check() allows/blocks ─────────────────────────────────────────────────────


def test_check_allows_under_limit():
    """N calls under the limit all succeed without raising."""
    limiter = make_limiter(per_ip=5)
    for _ in range(5):
        limiter.check(endpoint="/api/command", ip="1.2.3.4")  # should not raise


def test_check_blocks_at_limit():
    """The N+1th call raises HTTP 429."""
    limiter = make_limiter(per_ip=3)
    for _ in range(3):
        limiter.check(endpoint="/api/command", ip="10.0.0.1")
    with pytest.raises(HTTPException) as exc_info:
        limiter.check(endpoint="/api/command", ip="10.0.0.1")
    assert exc_info.value.status_code == 429


def test_check_unconfigured_endpoint_always_passes():
    """Endpoints with no config rule are never rate-limited."""
    limiter = make_limiter(endpoint="/api/command")
    for _ in range(100):
        limiter.check(endpoint="/api/other", ip="1.2.3.4")  # no rule → never raises


# ── reset() ───────────────────────────────────────────────────────────────────


def test_reset_clears_counters():
    """After reset(), calls are allowed again."""
    limiter = make_limiter(per_ip=2)
    for _ in range(2):
        limiter.check(endpoint="/api/command", ip="5.5.5.5")
    # Confirm we're at the limit
    with pytest.raises(HTTPException):
        limiter.check(endpoint="/api/command", ip="5.5.5.5")

    limiter.reset()
    # Should be allowed again after reset
    limiter.check(endpoint="/api/command", ip="5.5.5.5")  # no raise


# ── per-endpoint independence ─────────────────────────────────────────────────


def test_per_endpoint_limits():
    """Different endpoints have independent counters."""
    config = RateLimitConfig(
        limits=[
            EndpointLimit(endpoint="/api/a", per_ip=2, per_user=0, window_s=60),
            EndpointLimit(endpoint="/api/b", per_ip=2, per_user=0, window_s=60),
        ]
    )
    limiter = RateLimiter(config)

    # Exhaust /api/a
    for _ in range(2):
        limiter.check(endpoint="/api/a", ip="9.9.9.9")
    with pytest.raises(HTTPException):
        limiter.check(endpoint="/api/a", ip="9.9.9.9")

    # /api/b counter is independent — should still allow 2 more calls
    for _ in range(2):
        limiter.check(endpoint="/api/b", ip="9.9.9.9")


# ── init from config ──────────────────────────────────────────────────────────


def test_init_limiter_from_config():
    """RateLimitConfig.from_rcan() builds config from a dict."""
    rcan_config = {
        "rate_limits": [
            {"endpoint": "/api/command", "per_ip": 10, "per_user": 20, "window_s": 60},
            {"endpoint": "/api/webhook", "per_ip": 5, "per_user": 10, "window_s": 30},
        ]
    }
    cfg = RateLimitConfig.from_rcan(rcan_config)
    assert len(cfg.limits) == 2
    assert cfg.limits[0].endpoint == "/api/command"
    assert cfg.limits[0].per_ip == 10
    assert cfg.limits[1].window_s == 30.0


def test_init_limiter_from_config_empty():
    """from_rcan with no rate_limits key returns empty config."""
    cfg = RateLimitConfig.from_rcan({})
    assert cfg.limits == []


def test_init_limiter_from_config_invalid_entry():
    """Non-dict entries in rate_limits are skipped gracefully."""
    cfg = RateLimitConfig.from_rcan({"rate_limits": [None, "bad", {"endpoint": "/x", "per_ip": 3}]})
    assert len(cfg.limits) == 1


# ── singleton ─────────────────────────────────────────────────────────────────


def test_get_limiter_returns_singleton():
    """init_limiter sets and get_limiter returns the same instance."""
    config = {"rate_limits": [{"endpoint": "/api/cmd", "per_ip": 5}]}
    limiter1 = init_limiter(config)
    limiter2 = get_limiter()
    assert limiter1 is limiter2


def test_get_limiter_returns_none_before_init(monkeypatch):
    """get_limiter returns None if never initialised."""
    import castor.rate_limiting as rl

    monkeypatch.setattr(rl, "_default_limiter", None)
    assert get_limiter() is None


# ── per-user limits ───────────────────────────────────────────────────────────


def test_per_user_limit():
    """Per-user limit is enforced independently from per-IP."""
    config = RateLimitConfig(
        limits=[EndpointLimit(endpoint="/api/cmd", per_ip=0, per_user=3, window_s=60)]
    )
    limiter = RateLimiter(config)
    for _ in range(3):
        limiter.check(endpoint="/api/cmd", user="alice")
    with pytest.raises(HTTPException):
        limiter.check(endpoint="/api/cmd", user="alice")
    # bob is unaffected
    limiter.check(endpoint="/api/cmd", user="bob")
