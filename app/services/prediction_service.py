from uuid import uuid4

from app.config import Settings, get_settings
from app.schemas.prediction import RiskLevel, RiskScoreRequest, RiskScoreResponse

_LOW_THRESHOLD = 0.33
_MEDIUM_THRESHOLD = 0.66


def _bucket(score: float) -> RiskLevel:
    if score < _LOW_THRESHOLD:
        return "low"
    if score < _MEDIUM_THRESHOLD:
        return "medium"
    return "high"


class PredictionService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def score(self, request: RiskScoreRequest) -> RiskScoreResponse:
        ratio = request.debt / request.income
        risk_score = max(0.0, min(1.0, ratio))
        return RiskScoreResponse(
            request_id=uuid4(),
            risk_score=risk_score,
            risk_level=_bucket(risk_score),
            model_version=self._settings.model_version,
        )


def get_prediction_service() -> PredictionService:
    return PredictionService(settings=get_settings())
