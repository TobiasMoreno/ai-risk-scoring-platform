from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes import batch, health, metrics, predictions
from app.config import get_settings
from app.db.database import create_engine_from_settings, create_session_factory
from app.services.model_service import ModelService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    # Database first — if the DB is down, fail fast before loading the model.
    engine = create_engine_from_settings(settings)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    app.state.db_engine = engine
    app.state.session_factory = create_session_factory(engine)
    logger.info(
        "Database connected: pool_size=%d max_overflow=%d",
        settings.db_pool_size,
        settings.db_max_overflow,
    )

    # Model.
    model = ModelService(model_path=settings.model_path, model_version=settings.model_version)
    model.load()
    app.state.model_service = model

    try:
        yield
    finally:
        engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(predictions.router)
    app.include_router(batch.router)
    app.include_router(metrics.router)
    return app


app = create_app()
