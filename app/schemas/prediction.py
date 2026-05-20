from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["low", "medium", "high"]


class RiskScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    income: float = Field(gt=0, description="Ingreso mensual del solicitante (>0).")
    age: int = Field(ge=18, le=100, description="Edad del solicitante (18–100).")
    debt: float = Field(ge=0, description="Deuda total actual (≥0).")
    employment_years: int = Field(ge=0, description="Años de empleo continuos (≥0).")


class RiskScoreResponse(BaseModel):
    request_id: UUID
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    model_version: str
