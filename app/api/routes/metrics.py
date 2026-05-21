from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.repositories.prediction_repository import PredictionRepository
from app.schemas.prediction import SummaryResponse

router = APIRouter(tags=["metrics"])


@router.get("/metrics/summary", response_model=SummaryResponse)
def metrics_summary(session: Session = Depends(get_db)) -> SummaryResponse:
    stats = PredictionRepository(session).summary()
    return SummaryResponse(
        total=stats.total,
        avg_latency_ms=stats.avg_latency_ms,
        p95_latency_ms=stats.p95_latency_ms,
        by_risk_level=stats.by_risk_level,
        by_model_version=stats.by_model_version,
    )


@router.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
