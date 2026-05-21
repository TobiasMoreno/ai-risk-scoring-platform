from __future__ import annotations

import asyncio
import structlog
from sqlalchemy import text

from app.config import get_settings
from app.db.database import create_engine_from_settings, create_session_factory
from app.observability import configure_logging
from app.queue import RabbitConnection
from app.services.model_service import ModelService
from app.worker.consumer import consume_forever
from app.worker.recovery import run_recovery

logger = structlog.get_logger(__name__)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    engine = create_engine_from_settings(settings)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    session_factory = create_session_factory(engine)

    model = ModelService(
        model_path=settings.model_path,
        model_version=settings.model_version,
    )
    model.load()

    rabbit = RabbitConnection(settings)
    await rabbit.connect()
    logger.info("worker_connected", queue=settings.rabbitmq_queue_batch)

    try:
        await run_recovery(
            session_factory=session_factory,
            rabbit=rabbit,
            threshold_seconds=settings.batch_orphan_threshold_seconds,
        )
        await consume_forever(
            rabbit=rabbit,
            model_service=model,
            session_factory=session_factory,
            chunk_size=settings.batch_chunk_size,
            prefetch_count=settings.worker_prefetch_count,
        )
    finally:
        await rabbit.close()
        engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
