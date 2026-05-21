from __future__ import annotations

from io import BytesIO
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
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

INVALID_MIXED_CSV = (
    b"income,age,debt,employment_years,external_id\n"
    b"5000,30,800,4,ext-001\n"
    b"0,25,500,2,ext-002\n"
    b"8000,45,1200,15,ext-003\n"
    b"2000,,100,1,ext-004\n"
    b"12000,50,3000,20,ext-005\n"
)

ALL_INVALID_CSV = (
    b"income,age,debt,employment_years,external_id\n"
    b"0,30,800,4,ext-001\n"
    b"-1,25,500,2,ext-002\n"
    b"5000,17,500,2,ext-003\n"
)


async def _submit_and_process(
    client: AsyncClient, service: BatchService, csv_bytes: bytes
) -> UUID:
    files = {"file": ("in.csv", BytesIO(csv_bytes), "text/csv")}
    response = await client.post("/batch-predictions", files=files)
    assert response.status_code == 202
    job_id = UUID(response.json()["job_id"])
    service.process_job(job_id, csv_bytes)
    return job_id


@pytest.mark.anyio
async def test_full_happy_path_persists_all_rows(
    client_with_batch_db: AsyncClient,
    batch_service: BatchService,
    batch_session_factory: sessionmaker[Session],
) -> None:
    job_id = await _submit_and_process(
        client_with_batch_db, batch_service, VALID_CSV
    )

    with batch_session_factory() as s:
        job = s.execute(
            select(BatchJob).where(BatchJob.job_id == job_id)
        ).scalar_one()
        assert job.status == "COMPLETED"
        assert job.processed == 5
        assert job.failed == 0
        rows = s.execute(
            select(PredictionRequest).where(PredictionRequest.job_id == job_id)
        ).scalars().all()
        assert len(rows) == 5
        assert all(r.source == "batch" for r in rows)


@pytest.mark.anyio
async def test_invalid_rows_count_as_failed_but_job_completes(
    client_with_batch_db: AsyncClient,
    batch_service: BatchService,
    batch_session_factory: sessionmaker[Session],
) -> None:
    job_id = await _submit_and_process(
        client_with_batch_db, batch_service, INVALID_MIXED_CSV
    )

    with batch_session_factory() as s:
        job = s.execute(
            select(BatchJob).where(BatchJob.job_id == job_id)
        ).scalar_one()
        assert job.status == "COMPLETED"
        assert job.processed == 3
        assert job.failed == 2
        rows = s.execute(
            select(PredictionRequest).where(PredictionRequest.job_id == job_id)
        ).scalars().all()
        assert len(rows) == 3


@pytest.mark.anyio
async def test_all_invalid_rows_marks_job_failed(
    client_with_batch_db: AsyncClient,
    batch_service: BatchService,
    batch_session_factory: sessionmaker[Session],
) -> None:
    job_id = await _submit_and_process(
        client_with_batch_db, batch_service, ALL_INVALID_CSV
    )

    with batch_session_factory() as s:
        job = s.execute(
            select(BatchJob).where(BatchJob.job_id == job_id)
        ).scalar_one()
        assert job.status == "FAILED"
        assert job.processed == 0
        assert job.failed == 3
