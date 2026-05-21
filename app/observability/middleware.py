from __future__ import annotations

import time
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.observability.metrics import record_http_request, record_prediction_error

logger = structlog.get_logger(__name__)


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return str(path or request.url.path)


def install_observability_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            record_prediction_error("unhandled_http_exception")
            logger.exception(
                "http_request_failed",
                method=request.method,
                path=request.url.path,
            )
            raise
        finally:
            latency_seconds = time.perf_counter() - start
            route = _route_template(request)
            record_http_request(
                method=request.method,
                route=route,
                status_code=status_code,
                latency_seconds=latency_seconds,
            )
            logger.info(
                "http_request_completed",
                method=request.method,
                path=request.url.path,
                route=route,
                status_code=status_code,
                latency_ms=int(round(latency_seconds * 1000)),
            )
            if "response" in locals():
                response.headers["X-Request-ID"] = request_id
            clear_contextvars()
