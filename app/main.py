from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import health, predictions
from app.config import get_settings
from app.services.model_service import ModelService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    service = ModelService(
        model_path=settings.model_path,
        model_version=settings.model_version,
    )
    service.load()
    app.state.model_service = service
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(predictions.router)
    return app


app = create_app()
