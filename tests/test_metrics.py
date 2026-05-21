import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_summary_empty_returns_zeros(client_with_db: AsyncClient) -> None:
    response = await client_with_db.get("/metrics/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["avg_latency_ms"] == 0
    assert body["p95_latency_ms"] == 0
    assert body["by_risk_level"] == {"low": 0, "medium": 0, "high": 0}
    assert body["by_model_version"] == {}


@pytest.mark.anyio
async def test_summary_aggregates_predictions(client_with_db: AsyncClient) -> None:
    # Mix of low (small debt) and high (debt > income) → FakeModelService maps ratio.
    payloads = [
        {"income": 10000, "age": 30, "debt": 100, "employment_years": 5},  # low
        {"income": 10000, "age": 30, "debt": 100, "employment_years": 5},  # low
        {"income": 1000, "age": 40, "debt": 5000, "employment_years": 1},  # high
    ]
    for p in payloads:
        r = await client_with_db.post("/risk-score", json=p)
        assert r.status_code == 200

    response = await client_with_db.get("/metrics/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["by_risk_level"]["low"] == 2
    assert body["by_risk_level"]["high"] == 1
    assert body["by_risk_level"]["medium"] == 0
    assert body["by_model_version"]
    assert sum(body["by_model_version"].values()) == 3
    assert body["avg_latency_ms"] >= 0
    assert body["p95_latency_ms"] >= 0
