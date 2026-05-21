from __future__ import annotations

from io import BytesIO
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import BatchJob, PredictionRequest
from tests.conftest import FakeRabbitConnection

pytestmark = pytest.mark.integration

VALID_CSV = (
    b"income,age,debt,employment_years,external_id\n"
    b"5000,30,800,4,ext-001\n"
    b"3500,25,500,2,ext-002\n"
    b"8000,45,1200,15,ext-003\n"
    b"2000,22,100,1,ext-004\n"
    b"12000,50,3000,20,ext-005\n"
)


@pytest.mark.anyio
async def test_post_batch_happy_path_returns_202(
    client_with_batch_db: AsyncClient,
    fake_rabbit: FakeRabbitConnection,
    batch_session_factory: sessionmaker[Session],
) -> None:
    files = {"file": ("sample.csv", BytesIO(VALID_CSV), "text/csv")}
    response = await client_with_batch_db.post("/batch-predictions", files=files)

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["total_records"] == 5
    UUID(body["job_id"])
    assert response.headers.get("location") == f"/batch-predictions/{body['job_id']}"
    assert fake_rabbit.published_job_ids == [body["job_id"]]
    with batch_session_factory() as session:
        job = session.execute(
            select(BatchJob).where(BatchJob.job_id == UUID(body["job_id"]))
        ).scalar_one()
        assert job.csv_blob == VALID_CSV
        predictions = session.execute(select(PredictionRequest)).scalars().all()
        assert predictions == []


@pytest.mark.anyio
async def test_post_batch_missing_required_column_returns_422(
    client_with_batch_db: AsyncClient,
    fake_rabbit: FakeRabbitConnection,
) -> None:
    bad_csv = b"age,debt,employment_years,external_id\n30,100,4,ext-001\n"
    files = {"file": ("bad.csv", BytesIO(bad_csv), "text/csv")}
    response = await client_with_batch_db.post("/batch-predictions", files=files)

    assert response.status_code == 422
    assert fake_rabbit.published_job_ids == []


@pytest.mark.anyio
async def test_post_batch_oversized_returns_413(
    client_with_batch_db: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    fake_rabbit: FakeRabbitConnection,
) -> None:
    # Shrink the limit so we don't need to generate 10 MB of CSV in memory.
    from app import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("BATCH_MAX_UPLOAD_BYTES", "100")
    try:
        files = {"file": ("big.csv", BytesIO(VALID_CSV), "text/csv")}
        response = await client_with_batch_db.post("/batch-predictions", files=files)
        assert response.status_code == 413
        assert fake_rabbit.published_job_ids == []
    finally:
        config.get_settings.cache_clear()


@pytest.mark.anyio
async def test_post_batch_publish_failure_rolls_back_job(
    client_with_batch_db: AsyncClient,
    fake_rabbit: FakeRabbitConnection,
    batch_session_factory: sessionmaker[Session],
) -> None:
    fake_rabbit.fail_publish = True
    files = {"file": ("sample.csv", BytesIO(VALID_CSV), "text/csv")}
    response = await client_with_batch_db.post("/batch-predictions", files=files)

    assert response.status_code == 500
    with batch_session_factory() as session:
        count = len(session.execute(select(BatchJob)).scalars().all())
        assert count == 0
