from __future__ import annotations

from uuid import UUID

import anyio
from sqlalchemy.orm import Session, sessionmaker

from app.services.batch_service import BatchService
from app.services.model_service import ModelService


async def process_job(
    job_id: UUID,
    *,
    model_service: ModelService,
    session_factory: sessionmaker[Session],
    chunk_size: int,
) -> None:
    service = BatchService(
        model_service=model_service,
        session_factory=session_factory,
        chunk_size=chunk_size,
    )
    await anyio.to_thread.run_sync(service.process_job, job_id)
