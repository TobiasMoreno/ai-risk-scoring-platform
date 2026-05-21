## Why

Hoy el servicio sólo sirve predicciones de a una vía `POST /risk-score`. En la práctica, un consumidor del scoring va a querer correr lotes (revisión masiva, backfill, reproceso). S4 añade `POST /batch-predictions` con un CSV, persiste un `batch_jobs` con estado, y procesa las filas en background dentro del mismo proceso de la API. La elección de "in-proceso" es deliberada y temporal — S5 introduce la cola y el worker; aquí ya dejamos la state machine, la idempotencia y el modelo de datos listos para que ese cambio sea mecánico.

## What Changes

- **Schema**:
  - **NEW** tabla `batch_jobs` (`id BIGSERIAL PK`, `job_id UUID UNIQUE`, `status TEXT`, `total_records INTEGER`, `processed INTEGER DEFAULT 0`, `failed INTEGER DEFAULT 0`, `started_at TIMESTAMPTZ NULL`, `finished_at TIMESTAMPTZ NULL`, `created_at TIMESTAMPTZ DEFAULT now()`).
  - **ALTER** `prediction_requests`: añadir `job_id UUID NULL` (FK lógico a `batch_jobs.job_id`) y `external_id TEXT NULL`. Índice único parcial `(job_id, external_id) WHERE job_id IS NOT NULL AND external_id IS NOT NULL` — garantiza idempotencia por job sin afectar inserts online.
  - Default de `source` sigue siendo `'online'`; el batch usa `'batch'`.
- **State machine**: `PENDING → PROCESSING → (COMPLETED | FAILED)`. `FAILED` = todas las filas fallaron. Si hay al menos una predicción persistida, el job termina `COMPLETED` aunque algunas filas hayan fallado; el cliente ve `processed` vs `failed` para juzgar calidad.
- **Endpoints**:
  - `POST /batch-predictions` (multipart, campo `file` con CSV) → `202 Accepted` con `{job_id, status: "PENDING", total_records}`. Schedules el procesamiento con `BackgroundTasks` de FastAPI.
  - `GET /batch-predictions/{job_id}` → estado completo (`status`, `total_records`, `processed`, `failed`, `started_at`, `finished_at`, `created_at`). 404 si no existe.
  - `GET /batch-predictions/{job_id}/results?limit=&offset=` → filas persistidas para ese `job_id` (formato `PredictionRecordResponse`).
- **CSV**: headers requeridos `income,age,debt,employment_years,external_id`. `external_id` opcional por fila (si está vacío, la fila se procesa sin garantía de idempotencia). Encoding `utf-8`. Tamaño máximo configurable (default 10 MB) — más grande se rechaza con `413`.
- **Procesamiento**: stdlib `csv.DictReader` con chunks de tamaño configurable (default 1000). Cada chunk abre **su propia sesión** y commitea en lote, así un crash a mitad no tira los chunks anteriores. Filas con validación Pydantic fallida incrementan `failed`. Filas que violan el UNIQUE de idempotencia se cuentan como **ya procesadas** (no como `failed`).
- **Servicio**: nuevo `app/services/batch_service.py` con `create_job(stream, source) → BatchJob`, `process_job(job_id)` (idempotente: si ya está `COMPLETED` no hace nada), `get_status(job_id)`, `get_results(job_id, limit, offset)`.
- **Repositorio**: nuevo `BatchJobRepository` (`create`, `get_by_job_id`, `mark_processing`, `update_progress`, `mark_completed`, `mark_failed`). El `PredictionRepository.save` acepta los campos opcionales `job_id` y `external_id`; el constraint UNIQUE parcial se traduce a un `ON CONFLICT DO NOTHING` o a un `try/except IntegrityError` que reporta "skipped".
- **Tests** (integration): CSV happy path 5 filas con 5 inserts; CSV con 2 filas inválidas (1 422 + 1 missing field) que el job se completa con `failed=2`; idempotencia: reprocesar el mismo CSV no duplica; archivo > limit → 413. Fixture CSV en `tests/fixtures/`.
- **Docs**: README sección "Batch CSV"; ejemplo de upload con `curl -F file=@samples/sample_batch.csv`. `decisions.md` registra ADR-10 a ADR-13.

## Capabilities

### New Capabilities
<!-- Ninguna nueva: extiende risk-scoring-api. -->

### Modified Capabilities
- `risk-scoring-api`:
  - **MODIFIED** "Risk scoring (ML model)" — explicita que el endpoint sirve la ruta online; `source = "online"` y los registros persistidos no llevan `job_id`/`external_id`.
  - **ADDED** "Batch prediction submission" (POST /batch-predictions).
  - **ADDED** "Batch job status lookup" (GET /batch-predictions/{job_id}).
  - **ADDED** "Batch job results listing" (GET /batch-predictions/{job_id}/results).
  - **ADDED** "Batch idempotency per external_id" — descripción del invariante de unicidad y comportamiento al reprocesar.

## Impact

- **Código nuevo**: `app/db/models.py` (modelo `BatchJob` + columnas nuevas en `PredictionRequest`), `app/repositories/batch_job_repository.py`, `app/services/batch_service.py`, `app/api/routes/batch.py`, `tests/fixtures/sample_batch.csv`, nuevos tests.
- **Código modificado**: `app/repositories/prediction_repository.py` (acepta y persiste `job_id`/`external_id`), `app/schemas/prediction.py` (Pydantic `BatchJobResponse`, `BatchSubmitResponse`), `app/main.py` (registrar router), `app/config.py` (`batch_chunk_size`, `batch_max_upload_bytes`).
- **Migración Alembic**: una nueva revisión con `create_table('batch_jobs')`, `add_column('prediction_requests', 'job_id')`, `add_column('prediction_requests', 'external_id')`, índice único parcial.
- **Dependencias**: ninguna nueva (csv stdlib, FastAPI ya trae `UploadFile`).
- **Operativo**: el procesamiento bloquea threads del pool de FastAPI mientras corre. Aceptable para tamaños chicos; S5 lo mueve a cola.
- **Tag al cerrar**: `v0.4`.
