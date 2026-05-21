from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import BatchJob
from app.queue import RabbitConnection

logger = logging.getLogger(__name__)


async def run_recovery(
    *,
    session_factory: sessionmaker[Session],
    rabbit: RabbitConnection,
    threshold_seconds: int,
) -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=threshold_seconds)
    with session_factory() as session:
        rows = session.execute(
            select(BatchJob.job_id)
            .where(BatchJob.status == "PROCESSING")
            .where(BatchJob.started_at < cutoff)
            .order_by(BatchJob.started_at)
        ).scalars().all()

    recovered: list[str] = []
    for job_id in rows:
        await rabbit.publish_job(job_id)
        recovered.append(str(job_id))
        logger.info("batch job recovered job_id=%s", job_id)
    return recovered
