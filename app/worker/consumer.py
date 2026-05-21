from __future__ import annotations

import json
from json import JSONDecodeError
from uuid import UUID

import structlog
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.queue import RabbitConnection
from app.services.batch_service import BatchValidationError
from app.services.model_service import ModelService
from app.worker.processor import process_job

logger = structlog.get_logger(__name__)


async def handle_message(
    message,
    *,
    model_service: ModelService,
    session_factory: sessionmaker[Session],
    chunk_size: int,
) -> None:
    job_id: UUID | None = None
    try:
        payload = json.loads(message.body.decode("utf-8"))
        job_id = UUID(str(payload["job_id"]))
        logger.info("batch_job_consumed", job_id=str(job_id))
        await process_job(
            job_id,
            model_service=model_service,
            session_factory=session_factory,
            chunk_size=chunk_size,
        )
    except (JSONDecodeError, KeyError, ValueError, BatchValidationError) as exc:
        logger.warning(
            "batch_job_nacked",
            job_id=str(job_id) if job_id else None,
            requeue=False,
            error=str(exc),
        )
        await message.nack(requeue=False)
    except OperationalError as exc:
        logger.exception(
            "batch_job_nacked",
            job_id=str(job_id) if job_id else None,
            requeue=True,
            error=str(exc),
        )
        await message.nack(requeue=True)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "batch_job_nacked",
            job_id=str(job_id) if job_id else None,
            requeue=True,
            error=str(exc),
        )
        await message.nack(requeue=True)
    else:
        await message.ack()
        logger.info("batch_job_acked", job_id=str(job_id))


async def consume_forever(
    *,
    rabbit: RabbitConnection,
    model_service: ModelService,
    session_factory: sessionmaker[Session],
    chunk_size: int,
    prefetch_count: int,
) -> None:
    await rabbit.channel.set_qos(prefetch_count=prefetch_count)

    async with rabbit.queue.iterator() as queue_iter:
        async for message in queue_iter:
            await handle_message(
                message,
                model_service=model_service,
                session_factory=session_factory,
                chunk_size=chunk_size,
            )
import structlog
