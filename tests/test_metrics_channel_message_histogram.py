"""Tests for MetricsRegistry.channel_message_histogram() (#395)."""

import pytest

from castor.metrics import MetricsRegistry


@pytest.fixture
def registry():
    return MetricsRegistry()


# ── basic return shape ────────────────────────────────────────────────────────


def test_channel_message_histogram_returns_dict(registry):
    result = registry.channel_message_histogram()
    assert isinstance(result, dict)


def test_channel_message_histogram_has_buckets(registry):
    result = registry.channel_message_histogram()
    assert "buckets" in result


def test_channel_message_histogram_has_per_channel(registry):
    result = registry.channel_message_histogram()
    assert "per_channel" in result


def test_channel_message_histogram_empty_when_no_messages(registry):
    result = registry.channel_message_histogram()
    assert result["per_channel"] == {}


# ── bucket keys ───────────────────────────────────────────────────────────────


def test_histogram_has_inf_bucket(registry):
    result = registry.channel_message_histogram()
    assert "+Inf" in result["buckets"]


def test_histogram_has_numeric_buckets(registry):
    result = registry.channel_message_histogram()
    buckets = result["buckets"]
    expected = ["1", "5", "10", "50", "100", "500", "1000", "+Inf"]
    for b in expected:
        assert b in buckets, f"missing bucket: {b}"


# ── after recording messages ──────────────────────────────────────────────────


def test_per_channel_count_after_recording(registry):
    registry.record_channel_message("whatsapp")
    registry.record_channel_message("whatsapp")
    registry.record_channel_message("whatsapp")
    result = registry.channel_message_histogram()
    assert result["per_channel"].get("whatsapp") == 3


def test_per_channel_multiple_channels(registry):
    registry.record_channel_message("telegram")
    registry.record_channel_message("discord")
    registry.record_channel_message("discord")
    result = registry.channel_message_histogram()
    assert result["per_channel"]["telegram"] == 1
    assert result["per_channel"]["discord"] == 2


def test_inf_bucket_equals_total_channels(registry):
    for ch in ("a", "b", "c"):
        registry.record_channel_message(ch)
    result = registry.channel_message_histogram()
    assert result["buckets"]["+Inf"] == 3


# ── bucket cumulative counting ────────────────────────────────────────────────


def test_bucket_1_includes_channels_with_1_message(registry):
    registry.record_channel_message("single")
    result = registry.channel_message_histogram()
    assert result["buckets"]["1"] >= 1


def test_bucket_5_includes_channels_with_3_messages(registry):
    for _ in range(3):
        registry.record_channel_message("three_msgs")
    result = registry.channel_message_histogram()
    # 3 messages is ≤ 5, so it should appear in bucket "5"
    assert result["buckets"]["5"] >= 1


def test_bucket_1_excludes_channels_with_10_messages(registry):
    for _ in range(10):
        registry.record_channel_message("ten_msgs")
    result = registry.channel_message_histogram()
    assert result["buckets"]["1"] == 0


# ── count increments with each call ──────────────────────────────────────────


def test_count_increments_each_record(registry):
    registry.record_channel_message("slack")
    r1 = registry.channel_message_histogram()
    registry.record_channel_message("slack")
    r2 = registry.channel_message_histogram()
    assert r2["per_channel"]["slack"] == r1["per_channel"]["slack"] + 1


# ── never raises ─────────────────────────────────────────────────────────────


def test_channel_message_histogram_never_raises(registry):
    try:
        registry.channel_message_histogram()
    except Exception as exc:
        pytest.fail(f"channel_message_histogram raised: {exc}")
