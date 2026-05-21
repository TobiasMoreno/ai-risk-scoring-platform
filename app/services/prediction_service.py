from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.repositories.prediction_repository import PredictionRepository
from app.schemas.prediction import RiskScoreRequest, RiskScoreResponse
from app.services.model_service import ModelService, get_model_service


class PredictionService:
    def __init__(self, model: ModelService, repo: PredictionRepository) -> None:
        self._model = model
        self._repo = repo

    def score_and_persist(
        self, payload: RiskScoreRequest, source: str = "online"
    ) -> RiskScoreResponse:
        result = self._model.predict(payload)
        response = result.response
        self._repo.save(
            request_id=response.request_id,
            input_payload=payload.model_dump(),
            prediction={
                "risk_score": response.risk_score,
                "risk_level": response.risk_level,
                "model_version": response.model_version,
            },
            model_version=response.model_version,
            latency_ms=result.latency_ms,
            source=source,
        )
        return response


def get_prediction_service(
    session: Session = Depends(get_db),
    model: ModelService = Depends(get_model_service),
) -> PredictionService:
    return PredictionService(model=model, repo=PredictionRepository(session))
