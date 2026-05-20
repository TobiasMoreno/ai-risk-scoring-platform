from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.prediction import RiskScoreRequest, RiskScoreResponse
from app.services.model_service import ModelService, get_model_service

router = APIRouter(tags=["predictions"])


@router.post("/risk-score", response_model=RiskScoreResponse)
def create_risk_score(
    payload: RiskScoreRequest,
    service: ModelService = Depends(get_model_service),
) -> RiskScoreResponse:
    return service.predict(payload)


@router.get("/predictions/{prediction_id}")
def get_prediction(prediction_id: str) -> RiskScoreResponse:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Prediction lookup not implemented yet",
    )
