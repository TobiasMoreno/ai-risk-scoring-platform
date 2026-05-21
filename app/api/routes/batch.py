from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.schemas.batch import BatchJobResponse, BatchSubmitResponse
from app.schemas.prediction import PredictionRecordResponse
from app.services.batch_service import (
    BatchService,
    BatchTooLargeError,
    BatchValidationError,
)
from app.services.model_service import ModelService

router = APIRouter(tags=["batch"])


def _build_service(request: Request, settings: Settings) -> BatchService:
    model: ModelService = request.app.state.model_service
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    return BatchService(
        model_service=model,
        session_factory=session_factory,
        chunk_size=settings.batch_chunk_size,
    )


@router.post(
    "/batch-predictions",
    response_model=BatchSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_batch(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> BatchSubmitResponse:
    service = _build_service(request, settings)
    try:
        job, raw_bytes = service.create_job(
            stream=file.file, max_bytes=settings.batch_max_upload_bytes
        )
    except BatchTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    except BatchValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CSV must be UTF-8 encoded",
        ) from exc

    response.headers["Location"] = f"/batch-predictions/{job.job_id}"

    background_tasks.add_task(service.process_job, job.job_id, raw_bytes)

    return BatchSubmitResponse(
        job_id=job.job_id, status=job.status, total_records=job.total_records
    )


@router.get("/batch-predictions/{job_id}", response_model=BatchJobResponse)
def get_batch_job(
    job_id: UUID,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> BatchJobResponse:
    service = _build_service(request, settings)
    job = service.get_status(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch job {job_id} not found",
        )
    return BatchJobResponse(
        job_id=job.job_id,
        status=job.status,
        total_records=job.total_records,
        processed=job.processed,
        failed=job.failed,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
    )


@router.get(
    "/batch-predictions/{job_id}/results",
    response_model=list[PredictionRecordResponse],
)
def list_batch_results(
    job_id: UUID,
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    settings: Settings = Depends(get_settings),
) -> list[PredictionRecordResponse]:
    service = _build_service(request, settings)
    job, rows = service.get_results(job_id, limit=limit, offset=offset)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch job {job_id} not found",
        )
    return [
        PredictionRecordResponse(
            request_id=r.request_id,
            input_payload=r.input_payload,
            prediction=r.prediction,
            model_version=r.model_version,
            latency_ms=r.latency_ms,
            source=r.source,
            created_at=r.created_at,
            job_id=r.job_id,
            external_id=r.external_id,
        )
        for r in rows
    ]
