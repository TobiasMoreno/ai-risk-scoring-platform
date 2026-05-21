from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes import batch, health, metrics, predictions
from app.config import get_settings
from app.db.database import create_engine_from_settings, get_db
from app.schemas.prediction import RiskLevel, RiskScoreRequest, RiskScoreResponse
from app.services.batch_service import BatchService
from app.services.model_service import PredictionResult, get_model_service

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

    def predict(self, request: RiskScoreRequest) -> PredictionResult:
        ratio = request.debt / request.income
        score = float(max(0.0, min(1.0, ratio)))
        response = RiskScoreResponse(
            request_id=uuid4(),
            risk_score=score,
            risk_level=_bucket(score),
            model_version=self._model_version,
        )
        return PredictionResult(response=response, latency_ms=1)


def _build_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(health.router)
    app.include_router(predictions.router)
    app.include_router(batch.router)
    app.include_router(metrics.router)
    return app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ---------- Unit fixtures (no DB) ----------


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Client wired to a Fake model and a no-op DB session.

    Used by unit tests that don't care about persistence (validation, 422s, etc.).
    """
    app = _build_app()
    app.dependency_overrides[get_model_service] = lambda: FakeModelService()

    def _null_db():
        yield _NullSession()

    app.dependency_overrides[get_db] = _null_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class _NullSession:
    """No-op session for unit tests that should not touch DB. Calls become inert."""

    def add(self, *_args, **_kwargs) -> None:  # noqa: D401
        pass

    def flush(self) -> None:
        pass

    def execute(self, *_args, **_kwargs):
        raise RuntimeError("Unit test attempted a real DB query")

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


# ---------- Integration fixtures (require live Postgres) ----------


@pytest.fixture(scope="session")
def db_engine() -> Engine:
    settings = get_settings()
    try:
        engine = create_engine_from_settings(settings)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Postgres not available at {settings.database_url}: {exc}")
    return engine


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Function-scoped session with BEGIN/ROLLBACK isolation."""
    connection = db_engine.connect()
    trans = connection.begin()
    SessionFactory = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False)
    session = SessionFactory()
    try:
        # Make sure each test sees a clean table.
        session.execute(text("TRUNCATE TABLE prediction_requests RESTART IDENTITY"))
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture
async def client_with_db(db_session: Session) -> AsyncIterator[AsyncClient]:
    app = _build_app()
    app.dependency_overrides[get_model_service] = lambda: FakeModelService()

    def _override_db():
        # Yield the test-scoped session; do not commit (the outer transaction will rollback).
        try:
            yield db_session
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------- Batch fixtures: BackgroundTasks needs a real session_factory ----------


@pytest.fixture
def batch_session_factory(db_engine: Engine) -> Iterator[sessionmaker[Session]]:
    """Real session factory bound to the live engine (no BEGIN/ROLLBACK isolation).

    Batch jobs open their own sessions outside the request — they can't use
    the per-test transactional session. We TRUNCATE before and after each test.
    """
    factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    with factory() as s:
        s.execute(
            text("TRUNCATE TABLE prediction_requests, batch_jobs RESTART IDENTITY")
        )
        s.commit()
    try:
        yield factory
    finally:
        with factory() as s:
            s.execute(
                text("TRUNCATE TABLE prediction_requests, batch_jobs RESTART IDENTITY")
            )
            s.commit()


@pytest.fixture
async def client_with_batch_db(
    batch_session_factory: sessionmaker[Session],
) -> AsyncIterator[AsyncClient]:
    app = _build_app()
    fake_model = FakeModelService()
    app.state.model_service = fake_model
    app.state.session_factory = batch_session_factory
    app.dependency_overrides[get_model_service] = lambda: fake_model
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def batch_service(
    batch_session_factory: sessionmaker[Session],
) -> BatchService:
    return BatchService(
        model_service=FakeModelService(),
        session_factory=batch_session_factory,
        chunk_size=1000,
    )
