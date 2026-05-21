from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.repositories.prediction_repository import PredictionRepository

pytestmark = pytest.mark.integration


def _payload(income: float = 1000.0, debt: float = 500.0) -> dict:
    return {"income": income, "age": 30, "debt": debt, "employment_years": 3}


def _prediction(level: str = "low", score: float = 0.1, version: str = "v0.2.0") -> dict:
    return {"risk_score": score, "risk_level": level, "model_version": version}


def test_save_and_get_by_request_id(db_session: Session) -> None:
    repo = PredictionRepository(db_session)
    rid = uuid4()

    repo.save(
        request_id=rid,
        input_payload=_payload(),
        prediction=_prediction(),
        model_version="v0.2.0",
        latency_ms=12,
    )
    db_session.flush()

    row = repo.get_by_request_id(rid)
    assert row is not None
    assert row.model_version == "v0.2.0"
    assert row.latency_ms == 12
    assert row.source == "online"


def test_get_by_request_id_missing(db_session: Session) -> None:
    repo = PredictionRepository(db_session)
    assert repo.get_by_request_id(uuid4()) is None


def test_list_recent_orders_by_created_at_desc(db_session: Session) -> None:
    repo = PredictionRepository(db_session)
    ids = [uuid4() for _ in range(3)]
    for rid in ids:
        repo.save(
            request_id=rid,
            input_payload=_payload(),
            prediction=_prediction(),
            model_version="v0.2.0",
            latency_ms=5,
        )
        db_session.flush()

    rows = repo.list_recent(limit=10)
    assert [r.request_id for r in rows[:3]] == list(reversed(ids))


def test_summary_aggregates(db_session: Session) -> None:
    repo = PredictionRepository(db_session)
    for level, version, lat in [
        ("low", "v0.2.0", 5),
        ("low", "v0.2.0", 7),
        ("high", "test-1.0", 20),
    ]:
        repo.save(
            request_id=uuid4(),
            input_payload=_payload(),
            prediction=_prediction(level=level, version=version),
            model_version=version,
            latency_ms=lat,
        )
        db_session.flush()

    stats = repo.summary()
    assert stats.total == 3
    assert stats.by_risk_level == {"low": 2, "medium": 0, "high": 1}
    assert stats.by_model_version == {"v0.2.0": 2, "test-1.0": 1}
    assert stats.avg_latency_ms > 0
