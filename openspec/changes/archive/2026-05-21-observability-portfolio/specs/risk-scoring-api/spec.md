## MODIFIED Requirements

### Requirement: Predictions summary metrics
The system SHALL exponer `GET /metrics/summary` que devuelve agregados sobre `prediction_requests`. La respuesta MUST incluir: `total` (int), `avg_latency_ms` (float â‰¥ 0), `p95_latency_ms` (float â‰¥ 0), `by_risk_level` (objeto `{low: int, medium: int, high: int}`) y `by_model_version` (objeto `{<model_version>: int, ...}`).

The system SHALL also expose `GET /metrics` in Prometheus text exposition format. The response MUST include runtime metrics such as HTTP request counts/latency, prediction totals, model inference latency, prediction errors, batch job totals, and batch job duration. This endpoint MUST return a Prometheus-compatible content type.

#### Scenario: Returns aggregates over persisted predictions
- **GIVEN** existen predicciones persistidas con varios `model_version` y `risk_level`
- **WHEN** un cliente hace `GET /metrics/summary`
- **THEN** el servicio responde `200 OK` y `total` coincide con `COUNT(*)`, `avg_latency_ms` con el promedio, `by_risk_level` cubre los 3 buckets (cero si no hay registros) y `by_model_version` enumera todas las versiones presentes

#### Scenario: Empty table returns zeros
- **GIVEN** la tabla `prediction_requests` estÃ¡ vacÃ­a
- **WHEN** un cliente hace `GET /metrics/summary`
- **THEN** el servicio responde `200 OK` con `total = 0`, `avg_latency_ms = 0`, `p95_latency_ms = 0`, `by_risk_level = {low: 0, medium: 0, high: 0}`, `by_model_version = {}`

#### Scenario: Prometheus metrics are exposed
- **WHEN** un cliente hace `GET /metrics`
- **THEN** el servicio responde `200 OK` con formato Prometheus e incluye series `risk_predictions_total`, `risk_prediction_latency_seconds`, `risk_prediction_errors_total`, `risk_batch_jobs_total`, `risk_batch_job_duration_seconds`, y `risk_model_inference_latency_seconds`

## ADDED Requirements

### Requirement: Request correlation
The system SHALL assign a request correlation ID to every HTTP request. If the client sends `X-Request-ID`, the API MUST use that value; otherwise it MUST generate a UUID. The response MUST include the effective `X-Request-ID` header, and request logs MUST include the same value.

#### Scenario: Existing request ID is propagated
- **WHEN** a client sends `X-Request-ID: custom-id` to any API endpoint
- **THEN** the response includes `X-Request-ID: custom-id`

#### Scenario: Missing request ID is generated
- **WHEN** a client sends a request without `X-Request-ID`
- **THEN** the response includes a generated `X-Request-ID` value
