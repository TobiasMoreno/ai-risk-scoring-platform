from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from prometheus_client import generate_latest

from app.observability.metrics import BATCH_JOBS_TOTAL
from app.services.batch_service import BatchService

pytestmark = pytest.mark.integration

VALID_CSV = (
    b"income,age,debt,employment_years,external_id\n"
    b"5000,30,800,4,obs-001\n"
)


@pytest.mark.anyio
async def test_batch_terminal_metrics_are_recorded(
    client_with_batch_db: AsyncClient,
    batch_service: BatchService,
) -> None:
    before = BATCH_JOBS_TOTAL.labels(status="COMPLETED")._value.get()
    response = await client_with_batch_db.post(
        "/batch-predictions",
        files={"file": ("batch.csv", VALID_CSV, "text/csv")},
    )
    assert response.status_code == 202

    batch_service.process_job(UUID(response.json()["job_id"]))

    after = BATCH_JOBS_TOTAL.labels(status="COMPLETED")._value.get()
    assert after == before + 1
    body = generate_latest().decode("utf-8")
    assert "risk_batch_job_duration_seconds" in body
