from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PredictionRequest
from tests.conftest import TEST_MODEL_VERSION


pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_post_persists_row(client_with_db: AsyncClient, db_session: Session) -> None:
    payload = {"income": 5000, "age": 30, "debt": 800, "employment_years": 4}

    response = await client_with_db.post("/risk-score", json=payload)

    assert response.status_code == 200
    body = response.json()
    request_id = UUID(body["request_id"])

    row = db_session.execute(
        select(PredictionRequest).where(PredictionRequest.request_id == request_id)
    ).scalar_one()
    assert row.source == "online"
    assert row.model_version == TEST_MODEL_VERSION
    assert row.latency_ms >= 0
    assert row.input_payload["income"] == 5000
    assert row.prediction["risk_level"] == body["risk_level"]


@pytest.mark.anyio
async def test_get_by_request_id_returns_record(client_with_db: AsyncClient) -> None:
    payload = {"income": 5000, "age": 30, "debt": 200, "employment_years": 4}
    posted = await client_with_db.post("/risk-score", json=payload)
    request_id = posted.json()["request_id"]

    response = await client_with_db.get(f"/predictions/{request_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == request_id
    assert body["input_payload"]["income"] == 5000
    assert body["model_version"] == TEST_MODEL_VERSION
    assert body["source"] == "online"
    assert "created_at" in body


@pytest.mark.anyio
async def test_get_by_request_id_missing_returns_404(client_with_db: AsyncClient) -> None:
    response = await client_with_db.get(f"/predictions/{uuid4()}")

    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.anyio
async def test_get_with_invalid_uuid_returns_422(client_with_db: AsyncClient) -> None:
    response = await client_with_db.get("/predictions/not-a-uuid")

    assert response.status_code == 422


@pytest.mark.anyio
async def test_list_returns_recent_descending(client_with_db: AsyncClient) -> None:
    payloads = [
        {"income": 1000 + i, "age": 30, "debt": 100 + i, "employment_years": i}
        for i in range(3)
    ]
    ids = []
    for p in payloads:
        r = await client_with_db.post("/risk-score", json=p)
        ids.append(r.json()["request_id"])

    response = await client_with_db.get("/predictions?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    # Most recent first (last posted)
    assert body[0]["request_id"] == ids[-1]
    assert body[1]["request_id"] == ids[-2]


@pytest.mark.anyio
async def test_list_offset_pagination(client_with_db: AsyncClient) -> None:
    for i in range(5):
        await client_with_db.post(
            "/risk-score",
            json={"income": 1000 + i, "age": 30, "debt": 100 + i, "employment_years": i},
        )

    page1 = (await client_with_db.get("/predictions?limit=2&offset=0")).json()
    page2 = (await client_with_db.get("/predictions?limit=2&offset=2")).json()

    assert len(page1) == 2
    assert len(page2) == 2
    assert {r["request_id"] for r in page1}.isdisjoint({r["request_id"] for r in page2})


@pytest.mark.anyio
async def test_list_limit_out_of_range_returns_422(client_with_db: AsyncClient) -> None:
    response = await client_with_db.get("/predictions?limit=500")

    assert response.status_code == 422
