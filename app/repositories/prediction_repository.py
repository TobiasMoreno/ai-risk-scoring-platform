from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select, text
from sqlalchemy.orm import Session

from app.db.models import PredictionRequest


@dataclass
class SummaryStats:
    total: int
    avg_latency_ms: float
    p95_latency_ms: float
    by_risk_level: dict[str, int] = field(default_factory=dict)
    by_model_version: dict[str, int] = field(default_factory=dict)


class PredictionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        *,
        request_id: UUID,
        input_payload: dict[str, Any],
        prediction: dict[str, Any],
        model_version: str,
        latency_ms: int,
        source: str = "online",
    ) -> PredictionRequest:
        row = PredictionRequest(
            request_id=request_id,
            input_payload=input_payload,
            prediction=prediction,
            model_version=model_version,
            latency_ms=latency_ms,
            source=source,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get_by_request_id(self, request_id: UUID) -> PredictionRequest | None:
        stmt = select(PredictionRequest).where(PredictionRequest.request_id == request_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def list_recent(self, limit: int = 50, offset: int = 0) -> list[PredictionRequest]:
        stmt = (
            select(PredictionRequest)
            .order_by(desc(PredictionRequest.created_at), desc(PredictionRequest.id))
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.execute(stmt).scalars().all())

    def summary(self) -> SummaryStats:
        total_row = self._session.execute(
            select(
                func.count(PredictionRequest.id),
                func.coalesce(func.avg(PredictionRequest.latency_ms), 0.0),
                func.coalesce(
                    func.percentile_cont(0.95).within_group(
                        PredictionRequest.latency_ms.asc()
                    ),
                    0.0,
                ),
            )
        ).one()
        total = int(total_row[0] or 0)
        avg_latency = float(total_row[1] or 0.0)
        p95_latency = float(total_row[2] or 0.0)

        by_level: dict[str, int] = {"low": 0, "medium": 0, "high": 0}
        if total > 0:
            level_rows = self._session.execute(
                text(
                    "SELECT prediction->>'risk_level' AS lvl, COUNT(*) "
                    "FROM prediction_requests GROUP BY lvl"
                )
            ).all()
            for lvl, count in level_rows:
                if lvl in by_level:
                    by_level[lvl] = int(count)

        by_version: dict[str, int] = {}
        if total > 0:
            version_rows = self._session.execute(
                select(PredictionRequest.model_version, func.count(PredictionRequest.id))
                .group_by(PredictionRequest.model_version)
            ).all()
            by_version = {str(v): int(c) for v, c in version_rows}

        return SummaryStats(
            total=total,
            avg_latency_ms=avg_latency,
            p95_latency_ms=p95_latency,
            by_risk_level=by_level,
            by_model_version=by_version,
        )
