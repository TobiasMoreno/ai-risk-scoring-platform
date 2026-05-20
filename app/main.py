from fastapi import FastAPI

from app.api.routes import health, predictions
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(health.router)
    app.include_router(predictions.router)
    return app


app = create_app()
