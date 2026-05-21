from __future__ import annotations

import json
import logging
from json import JSONDecodeError
from uuid import UUID

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.queue import RabbitConnection
from app.services.batch_service import BatchValidationError
from app.services.model_service import ModelService
from app.worker.processor import process_job

logger = logging.getLogger(__name__)


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
        logger.info("batch job consumed job_id=%s", job_id)
        await process_job(
            job_id,
            model_service=model_service,
            session_factory=session_factory,
            chunk_size=chunk_size,
        )
    except (JSONDecodeError, KeyError, ValueError, BatchValidationError) as exc:
        logger.warning("batch job nacked requeue=false job_id=%s error=%s", job_id, exc)
        await message.nack(requeue=False)
    except OperationalError as exc:
        logger.exception("batch job nacked requeue=true job_id=%s error=%s", job_id, exc)
        await message.nack(requeue=True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("batch job nacked requeue=true job_id=%s error=%s", job_id, exc)
        await message.nack(requeue=True)
    else:
        await message.ack()
        logger.info("batch job acked job_id=%s", job_id)


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
