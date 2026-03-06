"""Tests for castor.webhooks — HMAC signing and dispatch logic (issue #484)."""

import hashlib
import hmac
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from castor.webhooks import (
    WebhookDispatcher,
    _dispatch_one,
    _sign_payload,
)

# ── Helper ────────────────────────────────────────────────────────────────────


def _make_response(status: int = 200):
    resp = MagicMock()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ── _sign_payload ─────────────────────────────────────────────────────────────


def test_sign_payload_known_vector():
    """HMAC-SHA256 of known input matches expected hex."""
    payload = b"hello world"
    secret = "my-secret"
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert _sign_payload(payload, secret) == expected
    # Also confirm it's a 64-char hex string
    assert len(expected) == 64


# ── _dispatch_one ─────────────────────────────────────────────────────────────


def test_dispatch_one_success():
    """_dispatch_one returns True when urlopen succeeds (200)."""
    mock_resp = _make_response(200)
    with patch("castor.webhooks.urllib.request.urlopen", return_value=mock_resp) as mock_open:
        result = _dispatch_one(
            url="https://example.com/hook",
            event="startup",
            data={},
            secret=None,
            timeout=5,
            retry=0,
        )
    assert result is True
    mock_open.assert_called_once()


def test_dispatch_one_retry_on_error():
    """_dispatch_one retries on URLError and eventually returns False."""
    call_count = 0

    def side_effect(req, timeout):
        nonlocal call_count
        call_count += 1
        raise URLError("connection refused")

    with patch("castor.webhooks.urllib.request.urlopen", side_effect=side_effect):
        with patch("castor.webhooks.time.sleep"):  # skip sleep delays
            result = _dispatch_one(
                url="https://example.com/hook",
                event="error",
                data={},
                secret=None,
                timeout=5,
                retry=2,
            )

    assert result is False
    assert call_count == 3  # 1 attempt + 2 retries


def test_dispatch_one_timeout():
    """_dispatch_one returns False on OSError (timeout equivalent)."""
    with patch("castor.webhooks.urllib.request.urlopen", side_effect=OSError("timed out")):
        with patch("castor.webhooks.time.sleep"):
            result = _dispatch_one(
                url="https://example.com/hook",
                event="error",
                data={},
                secret=None,
                timeout=1,
                retry=0,
            )
    assert result is False


def test_dispatch_one_success_after_retries():
    """_dispatch_one returns True when it succeeds on the last retry."""
    attempt = [0]
    mock_resp = _make_response(200)

    def side_effect(req, timeout):
        attempt[0] += 1
        if attempt[0] < 3:
            raise URLError("temporary failure")
        return mock_resp

    with patch("castor.webhooks.urllib.request.urlopen", side_effect=side_effect):
        with patch("castor.webhooks.time.sleep"):
            result = _dispatch_one(
                url="https://example.com/hook",
                event="command",
                data={},
                secret=None,
                timeout=5,
                retry=2,
            )

    assert result is True
    assert attempt[0] == 3


# ── WebhookDispatcher ─────────────────────────────────────────────────────────


def test_webhook_dispatcher_routes_event():
    """Event in webhook.events → dispatches; event NOT in list → skips."""
    mock_resp = _make_response(200)
    with patch("castor.webhooks.urllib.request.urlopen", return_value=mock_resp) as mock_open:
        dispatcher = WebhookDispatcher(
            [
                {"url": "https://example.com/hook", "events": ["startup", "error"], "retry": 0},
            ]
        )
        # Matching event
        results = dispatcher.emit_sync("startup", {})
        assert len(results) == 1
        assert results[0] is True

        # Non-matching event — should not dispatch
        mock_open.reset_mock()
        results2 = dispatcher.emit_sync("command", {})
        assert len(results2) == 0
        mock_open.assert_not_called()


def test_webhook_dispatcher_wildcard_event():
    """events: ['*'] dispatches for any event."""
    mock_resp = _make_response(200)
    with patch("castor.webhooks.urllib.request.urlopen", return_value=mock_resp):
        dispatcher = WebhookDispatcher(
            [
                {"url": "https://example.com/hook", "events": ["*"], "retry": 0},
            ]
        )
        results = dispatcher.emit_sync("estop", {})
        assert len(results) == 1
        assert results[0] is True


def test_webhook_dispatcher_adds_signature_header():
    """Webhook with secret → X-Castor-Signature header is present."""
    captured_req = {}

    def fake_urlopen(req, timeout):
        captured_req["headers"] = dict(req.headers)
        return _make_response(200)

    with patch("castor.webhooks.urllib.request.urlopen", side_effect=fake_urlopen):
        dispatcher = WebhookDispatcher(
            [
                {
                    "url": "https://example.com/hook",
                    "events": ["*"],
                    "secret": "s3cret",
                    "retry": 0,
                },
            ]
        )
        dispatcher.emit_sync("startup", {})

    # urllib lowercases headers
    header_keys = {k.lower() for k in captured_req["headers"]}
    assert "x-castor-signature" in header_keys
    sig = captured_req["headers"].get(
        "X-castor-signature", captured_req["headers"].get("x-castor-signature", "")
    )
    assert sig.startswith("sha256=")


def test_webhook_dispatcher_no_secret_no_header():
    """Webhook without secret → no X-Castor-Signature header."""
    captured_req = {}

    def fake_urlopen(req, timeout):
        captured_req["headers"] = dict(req.headers)
        return _make_response(200)

    with patch("castor.webhooks.urllib.request.urlopen", side_effect=fake_urlopen):
        dispatcher = WebhookDispatcher(
            [
                {"url": "https://example.com/hook", "events": ["*"], "retry": 0},
            ]
        )
        dispatcher.emit_sync("startup", {})

    header_keys = {k.lower() for k in captured_req["headers"]}
    assert "x-castor-signature" not in header_keys
