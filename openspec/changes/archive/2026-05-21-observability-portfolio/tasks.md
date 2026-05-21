## 1. Dependencies and Logging

- [x] 1.1 Add `prometheus-client` and `structlog` to `requirements.txt` and install them.
- [x] 1.2 Create `app/observability/__init__.py`.
- [x] 1.3 Create `app/observability/logging.py` with shared JSON logging configuration and request context binding.
- [x] 1.4 Configure API startup and worker startup to initialize structured logging.

## 2. Metrics Primitives

- [x] 2.1 Create `app/observability/metrics.py` with Prometheus counters/histograms for HTTP, predictions, errors, batch jobs, batch duration, and model inference latency.
- [x] 2.2 Add helper functions to record prediction outcomes, prediction errors, batch terminal status, and model inference duration.
- [x] 2.3 Ensure metric labels are bounded and never include `request_id`, `job_id`, `external_id`, or payload values.

## 3. API Observability

- [x] 3.1 Add FastAPI middleware that propagates or generates `X-Request-ID`.
- [x] 3.2 Middleware records HTTP request count, latency, and unhandled error metrics by method, route template, and status code.
- [x] 3.3 Middleware emits structured request completion logs with request_id, method, path, status_code, and latency_ms.
- [x] 3.4 Add `GET /metrics` endpoint returning Prometheus text exposition while keeping `/metrics/summary` unchanged.

## 4. Domain Instrumentation

- [x] 4.1 Instrument `ModelService.predict()` with `risk_model_inference_latency_seconds`.
- [x] 4.2 Instrument online predictions with `risk_predictions_total{model_version,risk_level,source}` and `risk_prediction_latency_seconds{source}`.
- [x] 4.3 Instrument prediction failures with `risk_prediction_errors_total{error_type}`.
- [x] 4.4 Instrument batch processor final states with `risk_batch_jobs_total{status}` and `risk_batch_job_duration_seconds`.
- [x] 4.5 Keep worker consumed/acked/nacked/recovered logs structured and carrying `job_id`.

## 5. Compose Observability Stack

- [x] 5.1 Add Prometheus service to `docker-compose.yml` with port `9090` and config volume.
- [x] 5.2 Add Grafana service to `docker-compose.yml` with port `3000`, persisted volume, and provisioning volumes.
- [x] 5.3 Create `infra/prometheus.yml` scraping API `/metrics`.
- [x] 5.4 Create Grafana datasource provisioning for Prometheus.
- [x] 5.5 Create Grafana dashboard provisioning with panels for prediction rate, latency, errors, risk-level distribution, and batch job status.

## 6. Tests

- [x] 6.1 Add tests that `GET /metrics` returns Prometheus content and expected metric names.
- [x] 6.2 Add tests for `X-Request-ID` propagation and generated response header.
- [x] 6.3 Add tests that online prediction increments prediction/model metrics without high-cardinality labels.
- [x] 6.4 Add tests for batch terminal metrics.
- [x] 6.5 Run full pytest suite with workspace basetemp.

## 7. Documentation and Wrap-up

- [x] 7.1 Update `README.md` into final portfolio format with observability URLs and demo flow.
- [x] 7.2 Update `docs/architecture.md` with final API/worker/RabbitMQ/Postgres/Prometheus/Grafana architecture.
- [x] 7.3 Add ADR for `structlog` + `prometheus-client` and deferring OpenTelemetry.
- [x] 7.4 Update `docs/roadmap.md` with future extensions: OpenTelemetry, alerting, drift detection, MLflow/model registry.
- [x] 7.5 Update `docs/semana-6.md` checklist and summary.
- [x] 7.6 Verify `openspec validate observability-portfolio` passes.
- [x] 7.7 Archive the change after implementation and tag `v1.0`.
