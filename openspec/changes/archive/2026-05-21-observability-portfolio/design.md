## Context

The platform now has a synchronous online prediction path, a durable batch path through RabbitMQ, PostgreSQL persistence, and a separate worker process. S6 needs to make the system observable enough to explain and debug in a portfolio setting: what is running, how fast it is, how many predictions/jobs succeeded or failed, and how requests can be correlated across logs.

Current state:
- `/metrics/summary` returns business aggregates from PostgreSQL, not Prometheus exposition.
- Logging uses the standard library with human-readable messages.
- Docker Compose runs Postgres, RabbitMQ, API, and worker, but no Prometheus/Grafana.
- Worker and API already share code paths for batch processing, which gives one place to instrument job outcomes.

## Goals / Non-Goals

**Goals:**
- Expose Prometheus metrics from the API at `/metrics`.
- Record HTTP request latency and error metrics through middleware.
- Record prediction, batch job, and model inference metrics at the domain layer.
- Emit structured JSON logs with request correlation for API requests and `job_id` for worker events.
- Add Prometheus and Grafana to Compose with provisioning checked into the repo.
- Update portfolio docs and decision notes.

**Non-Goals:**
- Full OpenTelemetry tracing across API, RabbitMQ, worker, and DB.
- Production-grade alerting rules.
- Authentication or network hardening for `/metrics`, Prometheus, or Grafana.
- Exact distributed tracing correlation from the HTTP submission request into worker execution.

## Decisions

### Decision 1: `prometheus-client` for metrics

Use the official Python `prometheus-client` package and expose metrics through FastAPI `Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)`.

Alternatives considered:
- Custom text formatting: too easy to get wrong and unnecessary.
- OpenTelemetry metrics: useful in production, but it adds collector/exporter complexity that does not improve this portfolio milestone.

### Decision 2: `structlog` JSON logs over custom formatter

Use `structlog` with stdlib logging integration. Configure it once at startup for API and worker. Logs should include timestamps, levels, logger name, event, and context fields such as `request_id`, `job_id`, `model_version`, and `latency_ms`.

Alternatives considered:
- Standard `logging` with hand-written JSON formatter: fewer dependencies, but context binding is worse and worker/API log consistency would require more code.
- Plain text logs: easier locally, weaker for portfolio and observability goals.

### Decision 3: Keep `/metrics/summary` and add `/metrics`

Keep the existing business summary endpoint unchanged. Add Prometheus exposition at `/metrics` in the same router.

Why:
- Existing tests and consumers continue to work.
- The two endpoints serve different audiences: `/metrics/summary` is an API response, `/metrics` is scraper input.

### Decision 4: Instrument at service boundaries

Metrics are recorded where outcomes are known:
- HTTP middleware records request count, latency, and uncaught exceptions.
- `ModelService.predict()` records model inference latency.
- `PredictionService.score_and_persist()` records online prediction totals by model version, risk level, and source.
- Batch processing records persisted row outcomes through the same prediction metric helper, and job terminal status/duration at final state.
- Worker consumer records ack/nack logs and can rely on processor metrics for job outcomes.

### Decision 5: Prometheus scrapes API; worker metrics are logged for now

In Compose, Prometheus scrapes the API `/metrics`. The worker process logs structured events and records domain metrics only if run in-process for tests; exposing a separate worker metrics HTTP server is deferred.

Why:
- The current worker is a simple long-running consumer with no HTTP server.
- Adding a second metrics server is feasible but not required for a clear S6 portfolio demo.
- Batch outcomes are visible from API metrics if the API process handles online metrics and DB summary endpoint covers persisted batch state. Worker logs cover execution events.

## Risks / Trade-offs

- **[Multi-process metric split]** -> API and worker do not share in-memory counters. Mitigation: document that `/metrics` is API-process metrics; batch persisted state remains queryable through DB summary/status endpoints.
- **[High-cardinality labels]** -> Avoid `request_id`, `job_id`, or endpoint path parameters as Prometheus labels. Use route templates and bounded labels only.
- **[Metrics reset on restart]** -> In-memory Prometheus counters reset when the process restarts. Acceptable for local portfolio; persisted aggregates remain in Postgres.
- **[JSON logs less readable locally]** -> Acceptable because Docker/Grafana/Prometheus workflow is the S6 goal.

## Migration Plan

1. Add dependencies and central observability modules.
2. Add middleware and `/metrics` endpoint.
3. Instrument online prediction, model inference, and batch processor final states.
4. Add Prometheus/Grafana Compose services and provisioning files.
5. Add tests for `/metrics`, request ID propagation, and metric labels.
6. Update README, architecture, decisions, roadmap, and S6 docs.

Rollback is straightforward: remove the middleware/router changes and Compose observability services. The data model does not change.
