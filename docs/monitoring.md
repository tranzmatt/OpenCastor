# Monitoring Stack — Prometheus, Grafana & Jaeger

OpenCastor ships a complete observability stack for fleet-scale deployments.

## Quick Start

```bash
# Start gateway + Prometheus + Grafana
docker compose --profile monitoring up

# Start everything + Jaeger (distributed traces)
docker compose --profile monitoring --profile otel up
```

| Service    | URL                         | Default credentials |
|------------|-----------------------------|---------------------|
| Prometheus | http://localhost:9090       | —                   |
| Grafana    | http://localhost:3000       | admin / opencastor  |
| Jaeger UI  | http://localhost:16686      | —                   |

## Metrics Endpoint

Every OpenCastor gateway exposes Prometheus metrics at `GET /api/metrics`:

```
opencastor_loops_total{robot="alex"} 1234
opencastor_action_latency_ms_bucket{...}
opencastor_brain_up{robot="alex"} 1
opencastor_driver_up{robot="alex"} 1
opencastor_uptime_seconds{robot="alex"} 3600
opencastor_safety_score{robot="alex"} 0.95
opencastor_provider_errors_total{provider="google",error_type="timeout"} 2
```

## Grafana Dashboard — 6 Panels

The pre-built dashboard (`docker/grafana/provisioning/dashboards/castor.json`)
includes:

1. **Loop Latency p50 / p95** — histogram quantiles
2. **Commands per Minute** — API command rate
3. **Provider Health** — safety score gauge
4. **Active Driver Mode** — current driver mode stat
5. **Error Rate by Code** — errors grouped by HTTP code / provider
6. **Memory Episodes Count** — total SQLite episode store size

## Configuration

### Prometheus Scrape Config

Edit `docker/prometheus/prometheus.yml` to add your robots:

```yaml
scrape_configs:
  - job_name: "my-robot"
    static_configs:
      - targets: ["my-robot.local:8000"]
    metrics_path: "/api/metrics"
    scrape_interval: 5s
```

### Pushgateway (Short-lived jobs)

Set `CASTOR_PROMETHEUS_PUSHGATEWAY` in `.env` to push metrics from batch jobs:

```bash
CASTOR_PROMETHEUS_PUSHGATEWAY=http://localhost:9091
```

Then call from Python:

```python
from castor.metrics import push_to_gateway
push_to_gateway(job="castor-batch-calibration")
```

### OpenTelemetry Traces

Set these environment variables to enable distributed tracing:

```bash
OTEL_SERVICE_NAME=my-robot
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OPENCASTOR_OTEL_EXPORTER=otlp
```

Then initialise in your startup code:

```python
from castor.telemetry import init_otel
init_otel()
```

## Embedding Metrics (`opencastor_embedding_*`)

The `EmbeddingInterpreter` emits its own Prometheus metrics for monitoring semantic
perception performance:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `opencastor_embedding_encode_total` | Counter | `backend`, `modality` | Total encode operations |
| `opencastor_embedding_encode_errors_total` | Counter | `backend`, `error_type` | Failed encodes by error class |
| `opencastor_embedding_latency_ms` | Histogram | `backend`, `modality` | Encode latency distribution |
| `opencastor_embedding_store_size` | Gauge | `backend` | Episode vector store size |
| `opencastor_embedding_rag_hits_total` | Counter | `backend` | RAG queries returning ≥1 result |

**Label values:**

- `backend`: `clip`, `siglip2`, `imagebind`, `clap`, `gemini`, `mock`
- `modality`: `image`, `audio`, `text`
- `error_type`: `timeout`, `decode_error`, `backend_unavailable`, `dimension_mismatch`

**Example Prometheus queries:**

```promql
# Embedding latency p95 by backend
histogram_quantile(0.95, rate(opencastor_embedding_latency_ms_bucket[5m]))

# Error rate for CLIP backend
rate(opencastor_embedding_encode_errors_total{backend="clip"}[5m])

# RAG hit rate (fraction of think() calls with memory context)
rate(opencastor_embedding_rag_hits_total[5m])
  / rate(opencastor_loops_total[5m])
```

Access the raw metrics:

```bash
curl http://localhost:8000/api/metrics | grep opencastor_embedding
```

Or check backend status:

```bash
curl http://localhost:8000/api/interpreter/status
# {"backend": "clip", "episode_count": 412, "dims": 512, "index_type": "faiss"}
```

→ See [embedding-interpreter.md](embedding-interpreter.md) for full EmbeddingInterpreter docs.

## RCAN Config

```yaml
telemetry:
  otel_endpoint: http://localhost:4317
  service_name: my-robot
  prometheus_pushgateway: http://localhost:9091
```
