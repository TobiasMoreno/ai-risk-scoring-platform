from __future__ import annotations

from io import BytesIO
from uuid import UUID

import pytest
from httpx import AsyncClient

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
) -> None:
    files = {"file": ("sample.csv", BytesIO(VALID_CSV), "text/csv")}
    response = await client_with_batch_db.post("/batch-predictions", files=files)

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["total_records"] == 5
    UUID(body["job_id"])
    assert response.headers.get("location") == f"/batch-predictions/{body['job_id']}"


@pytest.mark.anyio
async def test_post_batch_missing_required_column_returns_422(
    client_with_batch_db: AsyncClient,
) -> None:
    bad_csv = b"age,debt,employment_years,external_id\n30,100,4,ext-001\n"
    files = {"file": ("bad.csv", BytesIO(bad_csv), "text/csv")}
    response = await client_with_batch_db.post("/batch-predictions", files=files)

    assert response.status_code == 422


@pytest.mark.anyio
async def test_post_batch_oversized_returns_413(
    client_with_batch_db: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Shrink the limit so we don't need to generate 10 MB of CSV in memory.
    from app import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("BATCH_MAX_UPLOAD_BYTES", "100")
    try:
        files = {"file": ("big.csv", BytesIO(VALID_CSV), "text/csv")}
        response = await client_with_batch_db.post("/batch-predictions", files=files)
        assert response.status_code == 413
    finally:
        config.get_settings.cache_clear()
