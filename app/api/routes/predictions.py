from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.prediction import RiskScoreRequest, RiskScoreResponse
from app.services.prediction_service import PredictionService, get_prediction_service

router = APIRouter(tags=["predictions"])


@router.post("/risk-score", response_model=RiskScoreResponse)
def create_risk_score(
    payload: RiskScoreRequest,
    service: PredictionService = Depends(get_prediction_service),
) -> RiskScoreResponse:
    return service.score(payload)


@router.get("/predictions/{prediction_id}")
def get_prediction(prediction_id: str) -> RiskScoreResponse:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Prediction lookup not implemented yet",
    )
