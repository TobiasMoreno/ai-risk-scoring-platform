from __future__ import annotations

import csv
import io
import logging
import time
from typing import BinaryIO
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import BatchJob, PredictionRequest
from app.observability.metrics import record_batch_terminal, record_prediction
from app.repositories.batch_job_repository import BatchJobRepository
from app.repositories.prediction_repository import PredictionRepository
from app.schemas.prediction import RiskScoreRequest
from app.services.model_service import ModelService

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {"income", "age", "debt", "employment_years"}


class BatchValidationError(Exception):
    """Raised when the CSV payload cannot be accepted as a job."""


class BatchTooLargeError(Exception):
    """Raised when the upload exceeds the configured max size."""


def read_and_validate_csv(stream: BinaryIO, max_bytes: int) -> tuple[bytes, int]:
    raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise BatchTooLargeError(f"Upload exceeds {max_bytes} bytes")

    text_stream = io.StringIO(raw.decode("utf-8"))
    reader = csv.DictReader(text_stream)
    headers = set(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise BatchValidationError(f"Missing required CSV columns: {sorted(missing)}")

    total_records = sum(1 for _ in reader)
    return raw, total_records


class BatchService:
    def __init__(
        self,
        *,
        model_service: ModelService,
        session_factory: sessionmaker[Session],
        chunk_size: int = 1000,
    ) -> None:
        self._model = model_service
        self._session_factory = session_factory
        self._chunk_size = chunk_size

    # ---------- Submission ----------

    def create_job(
        self, stream: BinaryIO, max_bytes: int
    ) -> tuple[BatchJob, bytes]:
        raw, total_records = read_and_validate_csv(stream, max_bytes)

        job_id = uuid4()
        with self._session_factory() as session:
            repo = BatchJobRepository(session)
            job = repo.create(
                job_id=job_id, total_records=total_records, csv_blob=raw
            )
            session.commit()
            session.refresh(job)

        logger.info(
            "batch job created job_id=%s total_records=%d", job_id, total_records
        )
        return job, raw

    def create_job_in_session(
        self, session: Session, stream: BinaryIO, max_bytes: int
    ) -> tuple[BatchJob, bytes]:
        raw, total_records = read_and_validate_csv(stream, max_bytes)
        job_id = uuid4()
        job = BatchJobRepository(session).create(
            job_id=job_id, total_records=total_records, csv_blob=raw
        )
        logger.info(
            "batch job created job_id=%s total_records=%d", job_id, total_records
        )
        return job, raw

    # ---------- Processing ----------

    def process_job(self, job_id: UUID, raw_bytes: bytes | None = None) -> None:
        process_start = time.perf_counter()
        with self._session_factory() as session:
            repo = BatchJobRepository(session)
            job = repo.get_by_job_id(job_id)
            if job is None:
                logger.warning("process_job: job_id=%s not found", job_id)
                return
            if job.status in ("COMPLETED", "FAILED"):
                logger.info(
                    "process_job: job_id=%s already terminal status=%s; skipping",
                    job_id,
                    job.status,
                )
                return
            persisted_bytes = job.csv_blob
            if raw_bytes is None:
                raw_bytes = persisted_bytes
            if raw_bytes is None:
                repo.mark_failed(job_id)
                session.commit()
                record_batch_terminal(
                    "FAILED", time.perf_counter() - process_start
                )
                logger.error("process_job: job_id=%s has no csv_blob", job_id)
                return
            total_records = job.total_records
            repo.mark_processing(job_id)
            session.commit()

        try:
            text_stream = io.StringIO(raw_bytes.decode("utf-8"))
        except UnicodeDecodeError:
            with self._session_factory() as session:
                BatchJobRepository(session).mark_failed(job_id)
                session.commit()
            raise BatchValidationError("CSV must be UTF-8 encoded")

        reader = csv.DictReader(text_stream)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            with self._session_factory() as session:
                BatchJobRepository(session).mark_failed(job_id)
                session.commit()
            raise BatchValidationError(
                f"Missing required CSV columns: {sorted(missing)}"
            )

        chunk: list[dict[str, str]] = []
        chunk_index = 0
        total_processed = 0
        total_failed = 0

        for row in reader:
            chunk.append(row)
            if len(chunk) >= self._chunk_size:
                processed, failed = self._process_chunk(job_id, chunk, chunk_index)
                total_processed += processed
                total_failed += failed
                chunk_index += 1
                chunk = []

        if chunk:
            processed, failed = self._process_chunk(job_id, chunk, chunk_index)
            total_processed += processed
            total_failed += failed
            chunk_index += 1

        with self._session_factory() as session:
            repo = BatchJobRepository(session)
            if total_processed > 0 or total_records == 0:
                repo.mark_completed(job_id)
                final_status = "COMPLETED"
            else:
                repo.mark_failed(job_id)
                final_status = "FAILED"
            session.commit()
        record_batch_terminal(final_status, time.perf_counter() - process_start)

        logger.info(
            "batch job done job_id=%s status=%s total=%d processed=%d failed=%d",
            job_id,
            final_status,
            total_records,
            total_processed,
            total_failed,
        )

    def _process_chunk(
        self, job_id: UUID, chunk: list[dict[str, str]], chunk_index: int
    ) -> tuple[int, int]:
        processed = 0
        failed = 0

        with self._session_factory() as session:
            pred_repo = PredictionRepository(session)
            for row_offset, raw_row in enumerate(chunk):
                line_no = chunk_index * self._chunk_size + row_offset + 2  # +1 header +1 1-based
                external_id_raw = (raw_row.get("external_id") or "").strip()
                external_id = external_id_raw or None
                payload_dict = {
                    k: raw_row.get(k)
                    for k in ("income", "age", "debt", "employment_years")
                }
                try:
                    request = RiskScoreRequest(**payload_dict)
                except ValidationError as exc:
                    failed += 1
                    logger.warning(
                        "batch row invalid job_id=%s line=%d error=%s",
                        job_id,
                        line_no,
                        exc.errors(),
                    )
                    continue

                try:
                    result = self._model.predict(request)
                    response = result.response
                    inserted = pred_repo.save_batch_row(
                        request_id=response.request_id,
                        input_payload=request.model_dump(),
                        prediction={
                            "risk_score": response.risk_score,
                            "risk_level": response.risk_level,
                            "model_version": response.model_version,
                        },
                        model_version=response.model_version,
                        latency_ms=result.latency_ms,
                        job_id=job_id,
                        external_id=external_id,
                    )
                    if inserted:
                        processed += 1
                        record_prediction(
                            model_version=response.model_version,
                            risk_level=response.risk_level,
                            source="batch",
                            latency_ms=result.latency_ms,
                        )
                    else:
                        # Idempotency conflict — already processed, not a failure.
                        logger.info(
                            "batch row skipped (duplicate) job_id=%s line=%d external_id=%s",
                            job_id,
                            line_no,
                            external_id,
                        )
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    logger.exception(
                        "batch row error job_id=%s line=%d error=%s",
                        job_id,
                        line_no,
                        exc,
                    )

            session.commit()

            job_repo = BatchJobRepository(session)
            job_repo.update_progress(
                job_id, processed_delta=processed, failed_delta=failed
            )
            session.commit()

        logger.info(
            "batch chunk done job_id=%s chunk=%d processed=%d failed=%d",
            job_id,
            chunk_index,
            processed,
            failed,
        )
        return processed, failed

    # ---------- Lookups ----------

    def get_status(self, job_id: UUID) -> BatchJob | None:
        with self._session_factory() as session:
            job = BatchJobRepository(session).get_by_job_id(job_id)
            if job is not None:
                session.expunge(job)
            return job

    def get_results(
        self, job_id: UUID, limit: int, offset: int
    ) -> tuple[BatchJob | None, list[PredictionRequest]]:
        with self._session_factory() as session:
            job_repo = BatchJobRepository(session)
            job = job_repo.get_by_job_id(job_id)
            if job is None:
                return None, []
            pred_repo = PredictionRepository(session)
            rows = pred_repo.list_by_job(job_id, limit=limit, offset=offset)
            for r in rows:
                session.expunge(r)
            session.expunge(job)
            return job, rows
