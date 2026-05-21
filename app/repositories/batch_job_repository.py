from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.db.models import BatchJob


class BatchJobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, job_id: UUID, total_records: int) -> BatchJob:
        job = BatchJob(
            job_id=job_id,
            status="PENDING",
            total_records=total_records,
            processed=0,
            failed=0,
        )
        self._session.add(job)
        self._session.flush()
        return job

    def get_by_job_id(self, job_id: UUID) -> BatchJob | None:
        stmt = select(BatchJob).where(BatchJob.job_id == job_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def mark_processing(self, job_id: UUID) -> None:
        self._session.execute(
            update(BatchJob)
            .where(BatchJob.job_id == job_id)
            .values(status="PROCESSING", started_at=func.now())
        )

    def update_progress(
        self, job_id: UUID, *, processed_delta: int, failed_delta: int
    ) -> None:
        self._session.execute(
            update(BatchJob)
            .where(BatchJob.job_id == job_id)
            .values(
                processed=BatchJob.processed + processed_delta,
                failed=BatchJob.failed + failed_delta,
            )
        )

    def mark_completed(self, job_id: UUID) -> None:
        self._session.execute(
            update(BatchJob)
            .where(BatchJob.job_id == job_id)
            .values(status="COMPLETED", finished_at=func.now())
        )

    def mark_failed(self, job_id: UUID) -> None:
        self._session.execute(
            update(BatchJob)
            .where(BatchJob.job_id == job_id)
            .values(status="FAILED", finished_at=func.now())
        )
