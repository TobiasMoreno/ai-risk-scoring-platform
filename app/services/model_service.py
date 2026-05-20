from __future__ import annotations

import logging
import time
from pathlib import Path
from uuid import uuid4

import joblib
import numpy as np
from fastapi import Request
from sklearn.pipeline import Pipeline

from app.schemas.prediction import RiskLevel, RiskScoreRequest, RiskScoreResponse

logger = logging.getLogger(__name__)

_LOW_THRESHOLD = 0.33
_MEDIUM_THRESHOLD = 0.66
FEATURE_ORDER = ("income", "age", "debt", "employment_years")


def _bucket(score: float) -> RiskLevel:
    if score < _LOW_THRESHOLD:
        return "low"
    if score < _MEDIUM_THRESHOLD:
        return "medium"
    return "high"


class ModelService:
    def __init__(self, model_path: str, model_version: str) -> None:
        self._model_path = model_path
        self._model_version = model_version
        self._pipeline: Pipeline | None = None

    def load(self) -> None:
        path = Path(self._model_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Model file not found at {path}. Run `python -m app.models.train_model` first."
            )
        self._pipeline = joblib.load(path)
        logger.info(
            "Model loaded: version=%s path=%s", self._model_version, self._model_path
        )

    @property
    def model_version(self) -> str:
        return self._model_version

    def predict(self, request: RiskScoreRequest) -> RiskScoreResponse:
        if self._pipeline is None:
            raise RuntimeError("ModelService.predict() called before load()")
        features = np.array(
            [[getattr(request, name) for name in FEATURE_ORDER]], dtype=np.float64
        )
        start = time.perf_counter()
        proba = self._pipeline.predict_proba(features)[0, 1]
        latency_ms = (time.perf_counter() - start) * 1000.0
        risk_score = float(max(0.0, min(1.0, proba)))
        logger.info(
            "predict model_version=%s latency_ms=%.3f score=%.4f",
            self._model_version,
            latency_ms,
            risk_score,
        )
        return RiskScoreResponse(
            request_id=uuid4(),
            risk_score=risk_score,
            risk_level=_bucket(risk_score),
            model_version=self._model_version,
        )


def get_model_service(request: Request) -> ModelService:
    return request.app.state.model_service
