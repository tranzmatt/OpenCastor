"""Tests for WakeWordDetector (#394)."""

import pytest

from castor.hotword import WakeWordDetector


@pytest.fixture
def detector():
    return WakeWordDetector(wake_phrase="hey castor")


# ── instantiation ─────────────────────────────────────────────────────────────


def test_wakeword_detector_instantiates():
    d = WakeWordDetector()
    assert d is not None


def test_wakeword_detector_with_phrase():
    d = WakeWordDetector(wake_phrase="hey robot")
    assert d is not None


def test_wakeword_detector_has_engine(detector):
    assert hasattr(detector, "_engine")
    assert isinstance(detector._engine, str)


def test_wakeword_detector_engine_known_value(detector):
    assert detector._engine in ("sr", "openwakeword", "mock")


def test_wakeword_detector_initially_inactive(detector):
    assert detector._active is False


def test_wakeword_detector_detections_start_zero(detector):
    assert detector._detections == 0


# ── status() ─────────────────────────────────────────────────────────────────


def test_status_returns_dict(detector):
    result = detector.status
    assert isinstance(result, dict)


def test_status_has_active_key(detector):
    result = detector.status
    assert "active" in result


def test_status_has_engine_key(detector):
    result = detector.status
    assert "engine" in result


def test_status_has_detections_key(detector):
    result = detector.status
    assert "detections" in result


def test_status_active_false_initially(detector):
    result = detector.status
    assert result["active"] is False


def test_status_detections_zero_initially(detector):
    result = detector.status
    assert result["detections"] == 0


# ── start() / stop() ─────────────────────────────────────────────────────────


def test_start_sets_active_true(detector):
    try:
        detector.start()
        assert detector._active is True
    finally:
        detector.stop()


def test_stop_sets_active_false(detector):
    detector.start()
    detector.stop()
    assert detector._active is False


def test_start_twice_does_not_raise(detector):
    try:
        detector.start()
        detector.start()  # second call should be idempotent
    finally:
        detector.stop()


def test_stop_without_start_does_not_raise(detector):
    try:
        detector.stop()
    except Exception as exc:
        pytest.fail(f"stop() raised: {exc}")


def test_status_active_true_after_start(detector):
    try:
        detector.start()
        result = detector.status
        assert result["active"] is True
    finally:
        detector.stop()


def test_status_active_false_after_stop(detector):
    detector.start()
    detector.stop()
    result = detector.status
    assert result["active"] is False


# ── callback ─────────────────────────────────────────────────────────────────


def test_start_with_callback_does_not_raise(detector):
    called = []

    def on_wake():
        called.append(1)

    try:
        detector.start(on_wake=on_wake)
    finally:
        detector.stop()
