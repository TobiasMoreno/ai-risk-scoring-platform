from __future__ import annotations

from prometheus_client import Counter, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "risk_http_requests_total",
    "HTTP requests handled by the API.",
    ("method", "route", "status_code"),
)

HTTP_REQUEST_LATENCY_SECONDS = Histogram(
    "risk_http_request_latency_seconds",
    "HTTP request latency by route.",
    ("method", "route"),
)

PREDICTIONS_TOTAL = Counter(
    "risk_predictions_total",
    "Persisted risk predictions.",
    ("model_version", "risk_level", "source"),
)

PREDICTION_LATENCY_SECONDS = Histogram(
    "risk_prediction_latency_seconds",
    "End-to-end prediction latency by source.",
    ("source",),
)

PREDICTION_ERRORS_TOTAL = Counter(
    "risk_prediction_errors_total",
    "Prediction errors by bounded error type.",
    ("error_type",),
)

BATCH_JOBS_TOTAL = Counter(
    "risk_batch_jobs_total",
    "Batch jobs by terminal status.",
    ("status",),
)

BATCH_JOB_DURATION_SECONDS = Histogram(
    "risk_batch_job_duration_seconds",
    "Batch job processing duration.",
)

MODEL_INFERENCE_LATENCY_SECONDS = Histogram(
    "risk_model_inference_latency_seconds",
    "Model-only inference latency.",
)


def record_http_request(
    *, method: str, route: str, status_code: int, latency_seconds: float
) -> None:
    status = str(status_code)
    HTTP_REQUESTS_TOTAL.labels(method=method, route=route, status_code=status).inc()
    HTTP_REQUEST_LATENCY_SECONDS.labels(method=method, route=route).observe(
        latency_seconds
    )


def record_prediction(
    *,
    model_version: str,
    risk_level: str,
    source: str,
    latency_ms: int,
) -> None:
    PREDICTIONS_TOTAL.labels(
        model_version=model_version, risk_level=risk_level, source=source
    ).inc()
    PREDICTION_LATENCY_SECONDS.labels(source=source).observe(latency_ms / 1000.0)


def record_prediction_error(error_type: str) -> None:
    PREDICTION_ERRORS_TOTAL.labels(error_type=error_type).inc()


def record_batch_terminal(status: str, duration_seconds: float | None = None) -> None:
    BATCH_JOBS_TOTAL.labels(status=status).inc()
    if duration_seconds is not None and duration_seconds >= 0:
        BATCH_JOB_DURATION_SECONDS.observe(duration_seconds)


def record_model_inference(latency_seconds: float) -> None:
    MODEL_INFERENCE_LATENCY_SECONDS.observe(latency_seconds)
