from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import BatchJob, PredictionRequest
from app.repositories.batch_job_repository import BatchJobRepository
from app.worker.processor import process_job
from app.worker.recovery import run_recovery
from tests.conftest import FakeModelService, FakeRabbitConnection

pytestmark = [pytest.mark.integration, pytest.mark.worker]

VALID_CSV = (
    b"income,age,debt,employment_years,external_id\n"
    b"5000,30,800,4,ext-001\n"
    b"3500,25,500,2,ext-002\n"
    b"8000,45,1200,15,ext-003\n"
)

INVALID_BLOB = b"not,the,right,columns\n1,2,3,4\n"


@pytest.mark.anyio
async def test_processor_completes_job_from_persisted_blob(
    client_with_batch_db: AsyncClient,
    batch_session_factory: sessionmaker[Session],
) -> None:
    response = await client_with_batch_db.post(
        "/batch-predictions",
        files={"file": ("batch.csv", VALID_CSV, "text/csv")},
    )
    job_id = UUID(response.json()["job_id"])

    await process_job(
        job_id,
        model_service=FakeModelService(),
        session_factory=batch_session_factory,
        chunk_size=1000,
    )

    with batch_session_factory() as session:
        job = session.execute(
            select(BatchJob).where(BatchJob.job_id == job_id)
        ).scalar_one()
        assert job.status == "COMPLETED"
        assert job.processed == 3
        assert job.failed == 0
        assert job.csv_blob is None
        count = session.execute(
            select(func.count(PredictionRequest.id)).where(
                PredictionRequest.job_id == job_id
            )
        ).scalar_one()
        assert count == 3


@pytest.mark.anyio
async def test_recovery_republishes_only_old_processing_jobs(
    batch_session_factory: sessionmaker[Session],
) -> None:
    old_job = uuid4()
    recent_job = uuid4()
    pending_job = uuid4()
    with batch_session_factory() as session:
        repo = BatchJobRepository(session)
        old = repo.create(job_id=old_job, total_records=1, csv_blob=VALID_CSV)
        old.status = "PROCESSING"
        old.started_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        recent = repo.create(job_id=recent_job, total_records=1, csv_blob=VALID_CSV)
        recent.status = "PROCESSING"
        recent.started_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        repo.create(job_id=pending_job, total_records=1, csv_blob=VALID_CSV)
        session.commit()

    rabbit = FakeRabbitConnection()
    recovered = await run_recovery(
        session_factory=batch_session_factory,
        rabbit=rabbit,
        threshold_seconds=600,
    )

    assert recovered == [str(old_job)]
    assert rabbit.published_job_ids == [str(old_job)]


@pytest.mark.anyio
async def test_processor_marks_invalid_blob_failed(
    batch_session_factory: sessionmaker[Session],
) -> None:
    job_id = uuid4()
    with batch_session_factory() as session:
        BatchJobRepository(session).create(
            job_id=job_id, total_records=1, csv_blob=INVALID_BLOB
        )
        session.commit()

    with pytest.raises(Exception):
        await process_job(
            job_id,
            model_service=FakeModelService(),
            session_factory=batch_session_factory,
            chunk_size=1000,
        )

    with batch_session_factory() as session:
        job = session.execute(
            select(BatchJob).where(BatchJob.job_id == job_id)
        ).scalar_one()
        assert job.status == "FAILED"
        assert job.csv_blob is None
