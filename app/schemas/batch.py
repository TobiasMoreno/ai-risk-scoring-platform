from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

JobStatus = Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED"]


class BatchSubmitResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    total_records: int = Field(ge=0)


class BatchJobResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    total_records: int = Field(ge=0)
    processed: int = Field(ge=0)
    failed: int = Field(ge=0)
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
