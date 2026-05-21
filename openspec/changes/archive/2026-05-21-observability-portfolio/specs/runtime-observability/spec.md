## ADDED Requirements

### Requirement: Structured JSON logging
The system SHALL emit application logs as JSON objects for both API and worker processes. Each log record MUST include at least timestamp, level, logger, and event fields. API request logs MUST include `request_id`, method, path, status_code, and latency in milliseconds. Worker job logs MUST include `job_id` when a job is consumed, acknowledged, nacked, recovered, completed, or failed.

#### Scenario: API request log contains correlation fields
- **WHEN** an HTTP request completes
- **THEN** the API emits a JSON log with `request_id`, method, path, status_code, and latency_ms

#### Scenario: Worker job log contains job_id
- **WHEN** the worker consumes or completes a batch job
- **THEN** the worker emits a JSON log record containing the corresponding `job_id`

### Requirement: Prometheus runtime metrics
The system SHALL expose Prometheus metrics that cover HTTP traffic, prediction outcomes, model inference latency, prediction errors, batch job terminal states, and batch job duration. Metrics MUST use bounded labels only and MUST NOT include `request_id`, `job_id`, raw customer data, or external IDs as labels.

#### Scenario: Metrics include prediction totals
- **WHEN** an online or batch prediction is persisted
- **THEN** `risk_predictions_total` increments with labels `model_version`, `risk_level`, and `source`

#### Scenario: Metrics include model inference latency
- **WHEN** the model performs an inference
- **THEN** `risk_model_inference_latency_seconds` observes the inference duration

#### Scenario: Metrics avoid high-cardinality identifiers
- **WHEN** metrics are emitted for HTTP requests, predictions, or batch jobs
- **THEN** no metric label contains a request UUID, job UUID, external_id, or raw payload value

### Requirement: Batch job observability
The worker SHALL record observability signals when batch jobs reach terminal states. Completed and failed jobs MUST increment `risk_batch_jobs_total{status}` and observe total job duration in `risk_batch_job_duration_seconds` when timestamps allow it.

#### Scenario: Completed batch job records status and duration
- **WHEN** a batch job transitions to `COMPLETED`
- **THEN** `risk_batch_jobs_total{status="COMPLETED"}` increments and job duration is observed

#### Scenario: Failed batch job records status
- **WHEN** a batch job transitions to `FAILED`
- **THEN** `risk_batch_jobs_total{status="FAILED"}` increments

### Requirement: Local observability stack
The Compose stack SHALL include Prometheus and Grafana services. Prometheus MUST scrape the API `/metrics` endpoint. Grafana MUST start with a provisioned dashboard that includes panels for prediction rate, latency, errors, risk-level distribution, and batch job status.

#### Scenario: Compose starts observability services
- **WHEN** `docker compose up` starts the full stack
- **THEN** Prometheus is available on port 9090 and Grafana is available on port 3000

#### Scenario: Prometheus scrapes API metrics
- **WHEN** the API is running in Compose
- **THEN** Prometheus has a scrape job targeting the API `/metrics` endpoint
