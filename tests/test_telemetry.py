"""Unit tests for castor.telemetry (works without opentelemetry installed)."""

from __future__ import annotations


def test_has_otel_is_bool():
    from castor.telemetry import HAS_OTEL

    assert isinstance(HAS_OTEL, bool)


def test_private_has_otel_is_bool():
    import castor.telemetry as tel

    assert isinstance(tel._HAS_OTEL, bool)


def test_castor_telemetry_instantiates():
    from castor.telemetry import CastorTelemetry

    t = CastorTelemetry()
    assert t is not None


def test_init_otel_does_not_raise():
    from castor.telemetry import init_otel

    # Should not raise even if opentelemetry is not installed
    result = init_otel(service_name="test-service", exporter="console")
    assert isinstance(result, bool)


def test_trace_think_returns_context_manager():
    from castor.telemetry import trace_think

    span = trace_think(provider="test", model="fake", latency_ms=10.0, tokens=5)
    with span:
        pass  # must not raise


def test_trace_move_returns_context_manager():
    from castor.telemetry import trace_move

    span = trace_move(linear=0.5, angular=0.1, driver_mode="test")
    with span:
        pass  # must not raise


def test_get_telemetry_returns_singleton():
    from castor.telemetry import CastorTelemetry, get_telemetry

    t1 = get_telemetry()
    t2 = get_telemetry()
    assert isinstance(t1, CastorTelemetry)
    assert t1 is t2


# ---------------------------------------------------------------------------
# CastorTelemetry — noop counter / histogram / gauge operations
# ---------------------------------------------------------------------------


def test_castor_telemetry_record_action_no_otel():
    """record_action() runs without error when OTEL is absent (noop path)."""
    from castor.telemetry import CastorTelemetry

    t = CastorTelemetry()
    # Should not raise even with noop instruments
    t.record_action(latency_ms=50.0, action_type="move", provider="ollama")


def test_castor_telemetry_record_safety_score():
    """record_safety_score() stores the value on last_safety_score."""
    from castor.telemetry import CastorTelemetry

    t = CastorTelemetry()
    assert t.last_safety_score == 1.0  # initial default
    t.record_safety_score(0.72, robot_name="r2d2")
    assert t.last_safety_score == 0.72


def test_castor_telemetry_record_safety_violation():
    """record_safety_violation() does not raise with the noop counter."""
    from castor.telemetry import CastorTelemetry

    t = CastorTelemetry()
    t.record_safety_violation(violation_type="obstacle_too_close")


def test_castor_telemetry_record_brain_error():
    """record_brain_error() does not raise with the noop counter."""
    from castor.telemetry import CastorTelemetry

    t = CastorTelemetry()
    t.record_brain_error(provider="openai", error_type="timeout")


def test_castor_telemetry_enabled_false_initially():
    """A fresh CastorTelemetry instance starts as not enabled."""
    from castor.telemetry import CastorTelemetry

    t = CastorTelemetry()
    assert t.enabled is False


# ---------------------------------------------------------------------------
# CastorTelemetry.enable() — HAS_OTEL guard
# ---------------------------------------------------------------------------


def test_enable_returns_false_when_has_otel_false():
    """enable() returns False immediately when _HAS_OTEL is False."""
    from castor.telemetry import CastorTelemetry

    t = CastorTelemetry()
    with __import__("unittest.mock", fromlist=["patch"]).patch("castor.telemetry._HAS_OTEL", False):
        result = t.enable(service_name="test", exporter="console")

    assert result is False
    assert t.enabled is False


def test_enable_returns_false_for_exporter_none():
    """enable() returns False when exporter resolves to 'none'."""
    from castor.telemetry import CastorTelemetry

    t = CastorTelemetry()
    result = t.enable(service_name="test", exporter="none")
    assert result is False


def test_enable_returns_false_for_auto_with_no_env(monkeypatch):
    """enable(exporter='auto') with no env var resolves to 'none' → False."""
    from castor.telemetry import CastorTelemetry

    monkeypatch.delenv("OPENCASTOR_OTEL_EXPORTER", raising=False)
    t = CastorTelemetry()
    result = t.enable(service_name="test", exporter="auto")
    assert result is False


def test_enable_unknown_exporter_returns_false():
    """enable() returns False for an unrecognised exporter name when SDK present."""
    from unittest.mock import MagicMock, patch

    from castor.telemetry import CastorTelemetry

    t = CastorTelemetry()
    # Simulate the OTEL SDK being available by patching all required names
    mock_resource_instance = MagicMock()
    mock_resource_cls = MagicMock(create=MagicMock(return_value=mock_resource_instance))
    with (
        patch("castor.telemetry._HAS_OTEL", True),
        patch.dict(
            "castor.telemetry.__dict__",
            {
                "Resource": mock_resource_cls,
                "MeterProvider": MagicMock(),
                "PeriodicExportingMetricReader": MagicMock(),
                "_otel_metrics": MagicMock(),
                "ConsoleMetricExporter": MagicMock(),
            },
        ),
    ):
        result = t.enable(service_name="test", exporter="banana")

    assert result is False


# ---------------------------------------------------------------------------
# init_otel() — exporter='none' and absent SDK
# ---------------------------------------------------------------------------


def test_init_otel_returns_false_when_otel_trace_absent():
    """init_otel() returns False when the OTEL tracing SDK is not installed."""
    from castor.telemetry import init_otel

    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "castor.telemetry._HAS_OTEL_TRACE", False
    ):
        result = init_otel(service_name="test", exporter="console")

    assert result is False


def test_init_otel_returns_false_for_none_exporter():
    """init_otel(exporter='none') returns False without touching the SDK."""
    from castor.telemetry import init_otel

    # Works regardless of whether OTEL is installed
    result = init_otel(exporter="none")
    assert result is False


def test_init_otel_auto_resolves_to_none_by_default(monkeypatch):
    """init_otel(exporter='auto') resolves to 'none' when env var is absent."""
    monkeypatch.delenv("OPENCASTOR_OTEL_EXPORTER", raising=False)
    from castor.telemetry import init_otel

    result = init_otel(exporter="auto")
    assert result is False


# ---------------------------------------------------------------------------
# Noop shims — _NoopCounter, _NoopHistogram, _NoopGauge, _NoopSpan
# ---------------------------------------------------------------------------


def test_noop_counter_add_does_not_raise():
    """_NoopCounter.add() is a safe no-op."""
    from castor.telemetry import _NoopCounter

    c = _NoopCounter()
    c.add(1)
    c.add(5, attributes={"a": "b"})


def test_noop_histogram_record_does_not_raise():
    """_NoopHistogram.record() is a safe no-op."""
    from castor.telemetry import _NoopHistogram

    h = _NoopHistogram()
    h.record(100.5)
    h.record(0.0, attributes={"x": "y"})


def test_noop_gauge_set_does_not_raise():
    """_NoopGauge.set() is a safe no-op."""
    from castor.telemetry import _NoopGauge

    g = _NoopGauge()
    g.set(0.95)
    g.set(0.0, attributes={"robot": "r2"})


def test_noop_span_context_manager():
    """_NoopSpan works as a context manager and its methods do not raise."""
    from castor.telemetry import _NoopSpan

    span = _NoopSpan()
    with span:
        span.set_attribute("key", "value")
        span.record_exception(ValueError("boom"))
        span.set_status("OK")


# ---------------------------------------------------------------------------
# get_tracer and _NoopTracer
# ---------------------------------------------------------------------------


def test_get_tracer_returns_noop_tracer_when_not_initialised():
    """get_tracer() returns a _NoopTracer shim when no TracerProvider is set up."""
    import castor.telemetry as tel
    from castor.telemetry import _NoopTracer, get_tracer

    with (
        __import__("unittest.mock", fromlist=["patch"]).patch.object(tel, "_tracer", None),
        __import__("unittest.mock", fromlist=["patch"]).patch.object(tel, "_HAS_OTEL_TRACE", False),
    ):
        tracer = get_tracer()

    assert isinstance(tracer, _NoopTracer)


def test_noop_tracer_start_as_current_span_returns_noop_span():
    """_NoopTracer.start_as_current_span() returns a usable _NoopSpan."""
    from castor.telemetry import _NoopSpan, _NoopTracer

    tracer = _NoopTracer()
    span = tracer.start_as_current_span("test-span")
    assert isinstance(span, _NoopSpan)
    with span:
        pass  # must not raise


def test_noop_tracer_start_span_returns_noop_span():
    """_NoopTracer.start_span() returns a _NoopSpan."""
    from castor.telemetry import _NoopSpan, _NoopTracer

    tracer = _NoopTracer()
    span = tracer.start_span("another-span")
    assert isinstance(span, _NoopSpan)


# ---------------------------------------------------------------------------
# PrometheusRegistry (castor.telemetry.prometheus)
# ---------------------------------------------------------------------------


def test_prometheus_registry_instantiates():
    """PrometheusRegistry can be created without external dependencies."""
    from castor.telemetry.prometheus import PrometheusRegistry

    reg = PrometheusRegistry()
    assert reg is not None


def test_prometheus_inc_counter():
    """inc_counter() accumulates values correctly."""
    from castor.telemetry.prometheus import PrometheusRegistry

    reg = PrometheusRegistry()
    reg.inc_counter("opencastor_action_total", {"action_type": "move", "approved": "true"})
    reg.inc_counter("opencastor_action_total", {"action_type": "move", "approved": "true"})

    key = tuple(sorted({"action_type": "move", "approved": "true"}.items()))
    assert reg._counters["opencastor_action_total"][key] == 2.0


def test_prometheus_set_gauge():
    """set_gauge() overwrites the stored value."""
    from castor.telemetry.prometheus import PrometheusRegistry

    reg = PrometheusRegistry()
    reg.set_gauge("opencastor_battery_percent", 85.5)
    reg.set_gauge("opencastor_battery_percent", 72.0)

    key = ()
    assert reg._gauges["opencastor_battery_percent"][key] == 72.0


def test_prometheus_observe_histogram_accumulates():
    """observe_histogram() updates _sum and _count gauges."""
    from castor.telemetry.prometheus import PrometheusRegistry

    reg = PrometheusRegistry()
    reg.observe_histogram("opencastor_action_duration_ms", 100.0, {"action_type": "spin"})
    reg.observe_histogram("opencastor_action_duration_ms", 200.0, {"action_type": "spin"})

    key = (("action_type", "spin"),)
    assert reg._gauges["opencastor_action_duration_ms_sum"][key] == 300.0
    assert reg._gauges["opencastor_action_duration_ms_count"][key] == 2.0


def test_prometheus_record_action():
    """record_action() increments counter and histogram together."""
    from castor.telemetry.prometheus import PrometheusRegistry

    reg = PrometheusRegistry()
    reg.record_action("move", approved=True, duration_ms=55.0)

    key = tuple(sorted({"action_type": "move", "approved": "true"}.items()))
    assert reg._counters["opencastor_action_total"][key] == 1.0


def test_prometheus_record_safety_block():
    """record_safety_block() increments the safety blocks counter."""
    from castor.telemetry.prometheus import PrometheusRegistry

    reg = PrometheusRegistry()
    reg.record_safety_block("spin", "obstacle detected")

    key = tuple(sorted({"action_type": "spin", "reason": "obstacle detected"}.items()))
    assert reg._counters["opencastor_safety_blocks_total"][key] == 1.0


def test_prometheus_record_provider_latency():
    """record_provider_latency() accumulates latency histogram."""
    from castor.telemetry.prometheus import PrometheusRegistry

    reg = PrometheusRegistry()
    reg.record_provider_latency("openai", 120.0, model="gpt-4")
    reg.record_provider_latency("openai", 80.0, model="gpt-4")

    key = tuple(sorted({"provider": "openai", "model": "gpt-4"}.items()))
    assert reg._gauges["opencastor_provider_latency_ms_sum"][key] == 200.0


def test_prometheus_record_commitment():
    """record_commitment() increments the commitment records counter."""
    from castor.telemetry.prometheus import PrometheusRegistry

    reg = PrometheusRegistry()
    reg.record_commitment()
    reg.record_commitment()

    key = ()
    assert reg._counters["opencastor_commitment_records_total"][key] == 2.0


def test_prometheus_record_failover():
    """record_failover() increments the failover counter with correct labels."""
    from castor.telemetry.prometheus import PrometheusRegistry

    reg = PrometheusRegistry()
    reg.record_failover("openai", "anthropic")

    key = tuple(sorted({"from_provider": "openai", "to_provider": "anthropic"}.items()))
    assert reg._counters["opencastor_failover_total"][key] == 1.0


def test_prometheus_update_sensor():
    """update_sensor() sets distance and battery gauges."""
    from castor.telemetry.prometheus import PrometheusRegistry

    reg = PrometheusRegistry()
    reg.update_sensor(distance_mm=300.0, battery_pct=90.0)

    assert reg._gauges["opencastor_sensor_distance_mm"][()] == 300.0
    assert reg._gauges["opencastor_battery_percent"][()] == 90.0


def test_prometheus_update_uptime():
    """update_uptime() sets the uptime gauge to a positive value."""
    import time

    from castor.telemetry.prometheus import PrometheusRegistry

    reg = PrometheusRegistry()
    boot_time = time.time() - 42.0
    reg.update_uptime(boot_time)

    uptime = reg._gauges["opencastor_uptime_seconds"][()]
    assert uptime >= 42.0


def test_prometheus_render_contains_metric_names():
    """render() output includes HELP/TYPE headers for known metrics."""
    from castor.telemetry.prometheus import PrometheusRegistry

    reg = PrometheusRegistry()
    reg.inc_counter("opencastor_action_total", {"action_type": "move", "approved": "true"})
    reg.set_gauge("opencastor_battery_percent", 88.0)

    output = reg.render()
    assert "opencastor_action_total" in output
    assert "opencastor_battery_percent" in output
    assert "# HELP" in output
    assert "# TYPE" in output


def test_prometheus_render_format_labels():
    """_format_labels() produces correct Prometheus label syntax."""
    from castor.telemetry.prometheus import _format_labels

    result = _format_labels((("action_type", "move"), ("approved", "true")))
    assert result == '{action_type="move",approved="true"}'


def test_prometheus_format_labels_empty():
    """_format_labels() returns empty string for empty label tuples."""
    from castor.telemetry.prometheus import _format_labels

    assert _format_labels(()) == ""


def test_prometheus_get_registry_singleton():
    """get_registry() returns the same PrometheusRegistry instance each call."""
    from castor.telemetry.prometheus import PrometheusRegistry, get_registry

    r1 = get_registry()
    r2 = get_registry()
    assert isinstance(r1, PrometheusRegistry)
    assert r1 is r2


def test_prometheus_thread_safety():
    """inc_counter() is safe to call from multiple threads simultaneously."""
    import threading

    from castor.telemetry.prometheus import PrometheusRegistry

    reg = PrometheusRegistry()
    errors = []

    def worker():
        try:
            for _ in range(100):
                reg.inc_counter(
                    "opencastor_action_total", {"action_type": "spin", "approved": "true"}
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    key = tuple(sorted({"action_type": "spin", "approved": "true"}.items()))
    assert reg._counters["opencastor_action_total"][key] == 500.0
