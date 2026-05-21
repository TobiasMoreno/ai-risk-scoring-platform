from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.repositories.prediction_repository import PredictionRepository
from app.schemas.prediction import (
    PredictionRecordResponse,
    RiskScoreRequest,
    RiskScoreResponse,
)
from app.services.prediction_service import PredictionService, get_prediction_service

router = APIRouter(tags=["predictions"])


@router.post("/risk-score", response_model=RiskScoreResponse)
def create_risk_score(
    payload: RiskScoreRequest,
    service: PredictionService = Depends(get_prediction_service),
) -> RiskScoreResponse:
    return service.score_and_persist(payload)


@router.get("/predictions/{request_id}", response_model=PredictionRecordResponse)
def get_prediction(
    request_id: UUID,
    session: Session = Depends(get_db),
) -> PredictionRecordResponse:
    repo = PredictionRepository(session)
    row = repo.get_by_request_id(request_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prediction with request_id={request_id} not found",
        )
    return PredictionRecordResponse(
        request_id=row.request_id,
        input_payload=row.input_payload,
        prediction=row.prediction,
        model_version=row.model_version,
        latency_ms=row.latency_ms,
        source=row.source,
        created_at=row.created_at,
    )


@router.get("/predictions", response_model=list[PredictionRecordResponse])
def list_predictions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db),
) -> list[PredictionRecordResponse]:
    repo = PredictionRepository(session)
    rows = repo.list_recent(limit=limit, offset=offset)
    return [
        PredictionRecordResponse(
            request_id=r.request_id,
            input_payload=r.input_payload,
            prediction=r.prediction,
            model_version=r.model_version,
            latency_ms=r.latency_ms,
            source=r.source,
            created_at=r.created_at,
        )
        for r in rows
    ]
