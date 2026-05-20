from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import health, predictions
from app.config import get_settings
from app.schemas.prediction import RiskLevel, RiskScoreRequest, RiskScoreResponse
from app.services.model_service import get_model_service

_LOW_THRESHOLD = 0.33
_MEDIUM_THRESHOLD = 0.66

TEST_MODEL_VERSION = "test-1.0"


def _bucket(score: float) -> RiskLevel:
    if score < _LOW_THRESHOLD:
        return "low"
    if score < _MEDIUM_THRESHOLD:
        return "medium"
    return "high"


class FakeModelService:
    """Deterministic stand-in for ModelService. Avoids loading a real joblib."""

    def __init__(self, model_version: str = TEST_MODEL_VERSION) -> None:
        self._model_version = model_version

    @property
    def model_version(self) -> str:
        return self._model_version

    def predict(self, request: RiskScoreRequest) -> RiskScoreResponse:
        ratio = request.debt / request.income
        score = float(max(0.0, min(1.0, ratio)))
        return RiskScoreResponse(
            request_id=uuid4(),
            risk_score=score,
            risk_level=_bucket(score),
            model_version=self._model_version,
        )


def _make_app_without_lifespan() -> FastAPI:
    """Build the app without the real lifespan so tests don't need a .joblib."""
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(health.router)
    app.include_router(predictions.router)
    app.dependency_overrides[get_model_service] = lambda: FakeModelService()
    return app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    test_app = _make_app_without_lifespan()
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
