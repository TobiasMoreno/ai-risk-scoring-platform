from __future__ import annotations

from io import BytesIO
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

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


@pytest.mark.anyio
async def test_get_results_paginates(
    client_with_batch_db: AsyncClient,
    batch_service: BatchService,
) -> None:
    files = {"file": ("in.csv", BytesIO(VALID_CSV), "text/csv")}
    response = await client_with_batch_db.post("/batch-predictions", files=files)
    job_id = UUID(response.json()["job_id"])
    batch_service.process_job(job_id)

    page = await client_with_batch_db.get(
        f"/batch-predictions/{job_id}/results?limit=2&offset=2"
    )
    assert page.status_code == 200
    body = page.json()
    assert len(body) == 2
    for item in body:
        assert item["source"] == "batch"
        assert item["job_id"] == str(job_id)
        assert item["external_id"] in {"ext-001", "ext-002", "ext-003", "ext-004", "ext-005"}


@pytest.mark.anyio
async def test_get_job_status_completed(
    client_with_batch_db: AsyncClient,
    batch_service: BatchService,
) -> None:
    files = {"file": ("in.csv", BytesIO(VALID_CSV), "text/csv")}
    response = await client_with_batch_db.post("/batch-predictions", files=files)
    job_id = UUID(response.json()["job_id"])
    batch_service.process_job(job_id)

    status_resp = await client_with_batch_db.get(f"/batch-predictions/{job_id}")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["status"] == "COMPLETED"
    assert body["total_records"] == 5
    assert body["processed"] == 5
    assert body["failed"] == 0
    assert body["started_at"] is not None
    assert body["finished_at"] is not None


@pytest.mark.anyio
async def test_get_job_status_unknown_returns_404(
    client_with_batch_db: AsyncClient,
) -> None:
    response = await client_with_batch_db.get(f"/batch-predictions/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_job_results_unknown_returns_404(
    client_with_batch_db: AsyncClient,
) -> None:
    response = await client_with_batch_db.get(f"/batch-predictions/{uuid4()}/results")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_job_status_invalid_uuid_returns_422(
    client_with_batch_db: AsyncClient,
) -> None:
    response = await client_with_batch_db.get("/batch-predictions/not-a-uuid")
    assert response.status_code == 422
