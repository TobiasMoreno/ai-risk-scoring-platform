from uuid import UUID

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_risk_score_low(client: AsyncClient) -> None:
    payload = {"income": 10000, "age": 30, "debt": 1000, "employment_years": 5}

    response = await client.post("/risk-score", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "low"
    assert body["model_version"] == "mock-0.1"
    assert 0.0 <= body["risk_score"] <= 1.0
    assert body["risk_score"] == pytest.approx(0.1)
    UUID(body["request_id"])  # raises if not a valid UUID


@pytest.mark.anyio
async def test_risk_score_high_when_debt_exceeds_income(client: AsyncClient) -> None:
    payload = {"income": 1000, "age": 40, "debt": 5000, "employment_years": 2}

    response = await client.post("/risk-score", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["risk_score"] == 1.0
    assert body["risk_level"] == "high"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {"income": 0, "age": 30, "debt": 100, "employment_years": 1},
        {"income": -10, "age": 30, "debt": 100, "employment_years": 1},
        {"income": 1000, "age": 17, "debt": 100, "employment_years": 1},
        {"income": 1000, "age": 101, "debt": 100, "employment_years": 1},
        {"income": 1000, "age": 30, "debt": -1, "employment_years": 1},
        {"income": 1000, "age": 30, "debt": 100, "employment_years": -1},
    ],
)
async def test_risk_score_rejects_invalid_input(
    client: AsyncClient, payload: dict
) -> None:
    response = await client.post("/risk-score", json=payload)

    assert response.status_code == 422


@pytest.mark.anyio
async def test_risk_score_rejects_missing_field(client: AsyncClient) -> None:
    payload = {"income": 1000, "age": 30, "debt": 100}  # employment_years missing

    response = await client.post("/risk-score", json=payload)

    assert response.status_code == 422


@pytest.mark.anyio
async def test_get_prediction_returns_501(client: AsyncClient) -> None:
    response = await client.get("/predictions/abc")

    assert response.status_code == 501
    body = response.json()
    assert "detail" in body
    assert "not implemented" in body["detail"].lower()
