from __future__ import annotations

from io import BytesIO
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import BatchJob, PredictionRequest
from app.services.batch_service import BatchService

pytestmark = pytest.mark.integration

VALID_CSV = (
    b"income,age,debt,employment_years,external_id\n"
    b"5000,30,800,4,ext-001\n"
    b"3500,25,500,2,ext-002\n"
    b"8000,45,1200,15,ext-003\n"
    b"2000,22,100,1,ext-004\n"
    b"12000,50,3000,20,ext-005\n"
)

DUPLICATE_CSV = (
    b"income,age,debt,employment_years,external_id\n"
    b"5000,30,800,4,ext-001\n"
    b"3500,25,500,2,ext-002\n"
    b"8000,45,1200,15,ext-003\n"
    b"2000,22,100,1,ext-004\n"
    b"12000,50,3000,20,ext-001\n"
)


@pytest.mark.anyio
async def test_reprocessing_same_job_does_not_duplicate(
    client_with_batch_db: AsyncClient,
    batch_service: BatchService,
    batch_session_factory: sessionmaker[Session],
) -> None:
    files = {"file": ("in.csv", BytesIO(VALID_CSV), "text/csv")}
    response = await client_with_batch_db.post("/batch-predictions", files=files)
    job_id = UUID(response.json()["job_id"])

    batch_service.process_job(job_id, VALID_CSV)

    # Force the job back to PROCESSING and reprocess — exercises the UNIQUE
    # idempotency conflict path, not the "already terminal" short-circuit.
    with batch_session_factory() as s:
        job = s.execute(
            select(BatchJob).where(BatchJob.job_id == job_id)
        ).scalar_one()
        job.status = "PROCESSING"
        job.processed = 0
        s.commit()

    batch_service.process_job(job_id, VALID_CSV)

    with batch_session_factory() as s:
        count = s.execute(
            select(func.count(PredictionRequest.id)).where(
                PredictionRequest.job_id == job_id
            )
        ).scalar_one()
        assert count == 5


@pytest.mark.anyio
async def test_duplicate_external_id_within_job_is_skipped(
    client_with_batch_db: AsyncClient,
    batch_service: BatchService,
    batch_session_factory: sessionmaker[Session],
) -> None:
    files = {"file": ("dup.csv", BytesIO(DUPLICATE_CSV), "text/csv")}
    response = await client_with_batch_db.post("/batch-predictions", files=files)
    job_id = UUID(response.json()["job_id"])

    batch_service.process_job(job_id, DUPLICATE_CSV)

    with batch_session_factory() as s:
        job = s.execute(
            select(BatchJob).where(BatchJob.job_id == job_id)
        ).scalar_one()
        assert job.status == "COMPLETED"
        # 4 inserted (one ext-001 collision skipped); failed counter not bumped.
        assert job.processed == 4
        assert job.failed == 0
        count = s.execute(
            select(func.count(PredictionRequest.id)).where(
                PredictionRequest.job_id == job_id
            )
        ).scalar_one()
        assert count == 4


@pytest.mark.anyio
async def test_terminal_job_is_not_reprocessed(
    client_with_batch_db: AsyncClient,
    batch_service: BatchService,
    batch_session_factory: sessionmaker[Session],
) -> None:
    files = {"file": ("in.csv", BytesIO(VALID_CSV), "text/csv")}
    response = await client_with_batch_db.post("/batch-predictions", files=files)
    job_id = UUID(response.json()["job_id"])

    batch_service.process_job(job_id, VALID_CSV)
    # Second call should be a no-op because status is COMPLETED.
    batch_service.process_job(job_id, VALID_CSV)

    with batch_session_factory() as s:
        count = s.execute(
            select(func.count(PredictionRequest.id)).where(
                PredictionRequest.job_id == job_id
            )
        ).scalar_one()
        assert count == 5
