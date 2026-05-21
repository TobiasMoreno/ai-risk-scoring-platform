## Why

S6 turns the platform from a working demo into something presentable as an AI/ML backend portfolio project. The API and worker already process online and batch predictions, but they do not yet expose operational signals, structured logs, or a final runbook that shows how to observe the system.

## What Changes

- Add Prometheus instrumentation for online predictions, batch jobs, request latency, errors, and model inference latency.
- Expose `GET /metrics` in Prometheus text format.
- Add request middleware that assigns or propagates `X-Request-ID`, logs request lifecycle events, and records HTTP latency.
- Add JSON logging configuration shared by API and worker.
- Add Prometheus and Grafana services to Docker Compose, including a provisioned dashboard.
- Update documentation for the final portfolio state: architecture, README, decisions, roadmap, and S6 notes.
- No public breaking changes to prediction APIs.

## Capabilities

### New Capabilities
- `runtime-observability`: Prometheus metrics, structured JSON logs, request correlation, and dashboard provisioning for API and worker runtime behavior.

### Modified Capabilities
- `risk-scoring-api`: add the Prometheus `/metrics` endpoint and request correlation header behavior to the HTTP API contract.

## Impact

- **Code**: `app/main.py`, `app/api/routes/metrics.py`, prediction and batch processing services, worker consumer/processor, new observability modules.
- **Dependencies**: add `prometheus-client` and `structlog`. OpenTelemetry is documented as a future extension rather than included in S6 to keep the portfolio deploy simple.
- **Infra**: `docker-compose.yml` gains `prometheus` and `grafana`; new `infra/` config files provision Prometheus scrape targets and a Grafana dashboard.
- **Docs**: README, architecture, decisions, roadmap, and S6 notes are updated to describe the final observable system.
