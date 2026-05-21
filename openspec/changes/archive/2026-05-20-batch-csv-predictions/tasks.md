## 1. Schema y migración

- [x] 1.1 Añadir modelo `BatchJob` a `app/db/models.py` (`id BIGSERIAL`, `job_id UUID UNIQUE`, `status String`, `total_records Integer`, `processed Integer default 0`, `failed Integer default 0`, `started_at TIMESTAMPTZ NULL`, `finished_at TIMESTAMPTZ NULL`, `created_at TIMESTAMPTZ default now()`)
- [x] 1.2 Añadir columnas a `PredictionRequest`: `job_id UUID NULL`, `external_id String NULL`
- [x] 1.3 Añadir índice único parcial `(job_id, external_id) WHERE job_id IS NOT NULL AND external_id IS NOT NULL`. Como Alembic autogen no lo detecta bien, escribirlo a mano en la revisión
- [x] 1.4 `alembic revision --autogenerate -m "batch_jobs and idempotency columns"`; editar el archivo para asegurar índice parcial y orden de operaciones
- [x] 1.5 `alembic upgrade head` contra DB local; verificar con `\d batch_jobs` y `\d prediction_requests`

## 2. Settings

- [x] 2.1 `app/config.py`: añadir `batch_chunk_size: int = 1000`, `batch_max_upload_bytes: int = 10 * 1024 * 1024`
- [x] 2.2 `.env.example`: documentar `BATCH_CHUNK_SIZE` y `BATCH_MAX_UPLOAD_BYTES`

## 3. Schemas Pydantic

- [x] 3.1 `app/schemas/batch.py`: `BatchSubmitResponse` (`job_id`, `status`, `total_records`)
- [x] 3.2 Mismo archivo: `BatchJobResponse` (todos los campos del job)
- [x] 3.3 `app/schemas/prediction.py`: extender `PredictionRecordResponse` con `external_id: str | None`, `job_id: UUID | None`
- [x] 3.4 Constantes `JobStatus = Literal["PENDING","PROCESSING","COMPLETED","FAILED"]`

## 4. Repositorios

- [x] 4.1 `app/repositories/batch_job_repository.py`: `BatchJobRepository(session)` con `create(job_id, total_records) -> BatchJob`, `get_by_job_id(uuid) -> BatchJob | None`, `mark_processing(job_id)`, `update_progress(job_id, processed_delta, failed_delta)`, `mark_completed(job_id)`, `mark_failed(job_id)`
- [x] 4.2 `PredictionRepository.save(...)` acepta `job_id: UUID | None = None`, `external_id: str | None = None`
- [x] 4.3 Nuevo método `PredictionRepository.save_batch_row(...) -> bool` que usa `insert(...).on_conflict_do_nothing(index_elements=[...])` (psql dialect) y devuelve `True` si insertó, `False` si fue conflict
- [x] 4.4 `PredictionRepository.list_by_job(job_id, limit, offset) -> list[PredictionRequest]` ordenado por `created_at ASC, id ASC`

## 5. BatchService

- [x] 5.1 `app/services/batch_service.py`: clase `BatchService` con dependencias `model_service` y `session_factory` (el servicio crea sus propias sesiones — corre fuera del request)
- [x] 5.2 Método `create_job(stream: BinaryIO, max_bytes: int) -> BatchJob`: valida tamaño (lee `stream.read(max_bytes + 1)` y compara), parsea headers (DictReader), verifica columnas requeridas, cuenta filas, persiste `BatchJob` PENDING. Devuelve `(job, raw_bytes)` para que el endpoint pase el contenido al BackgroundTask
- [x] 5.3 Método `process_job(job_id: UUID, raw_bytes: bytes)`: idempotente respecto al estado del job — si ya `COMPLETED`/`FAILED`, log y return. Mark `PROCESSING` + `started_at`. Itera el CSV en chunks (config `batch_chunk_size`), en cada chunk: para cada fila, valida con `RiskScoreRequest`, si OK invoca `model.predict()` y `repo.save_batch_row(...)`; cuenta resultados. Update progreso por chunk. Al final: `mark_completed` si `processed > 0` o `total_records == 0`, else `mark_failed`. Loguear cierre del job
- [x] 5.4 Método `get_status(job_id)`, `get_results(job_id, limit, offset)` — wrappers sobre repos

## 6. Endpoints

- [x] 6.1 `app/api/routes/batch.py`: `POST /batch-predictions` con `file: UploadFile = File(...)` y `background_tasks: BackgroundTasks`. Valida tamaño, llama `BatchService.create_job`, devuelve `202` + header `Location: /batch-predictions/{job_id}`. Schedule `process_job(job.job_id, raw_bytes)` en BackgroundTasks
- [x] 6.2 `GET /batch-predictions/{job_id}` (path UUID) → `BatchJobResponse` o 404
- [x] 6.3 `GET /batch-predictions/{job_id}/results?limit=&offset=` → lista de `PredictionRecordResponse` o 404 si el job no existe. Validar `limit∈[1,200]`, `offset≥0`
- [x] 6.4 Registrar el router en `app/main.py`

## 7. Inyección y session-handling fuera del request

- [x] 7.1 `BatchService.process_job` corre **después** del request → no puede usar la sesión inyectada. Crea sesión propia desde `app.state.session_factory` (pasarla por DI al construir el servicio, o capturar `request.app.state` y guardarla en el background task)
- [x] 7.2 Implementar como factory: el router pasa al BackgroundTask una función que toma el `SessionLocal` desde `request.app.state` por closure

## 8. CSV fixture

- [x] 8.1 `tests/fixtures/sample_batch.csv`: 5 filas válidas con `external_id` distintos
- [x] 8.2 `tests/fixtures/sample_batch_with_invalid.csv`: 5 filas, 2 inválidas (income=0, missing age)
- [x] 8.3 `tests/fixtures/sample_batch_duplicate.csv`: 5 filas con un `external_id` repetido

## 9. Tests

- [x] 9.1 Marcar todos los tests nuevos como `@pytest.mark.integration` (necesitan DB)
- [x] 9.2 Fixture que recibe `client_with_db` y permite ejecutar el BackgroundTask sincrónicamente (override del schedule del FastAPI BackgroundTasks o usar el endpoint y luego esperar a que el job termine; alternativa: invocar `BatchService.process_job` directo desde el test después del POST)
- [x] 9.3 `tests/test_batch_submit.py`: POST happy path → 202, job creado, total_records=5
- [x] 9.4 Mismo archivo: POST sin columna `income` → 422
- [x] 9.5 Mismo archivo: POST con archivo > 10 MB → 413 (generar un CSV grande en memoria o ajustar `batch_max_upload_bytes` vía settings/override)
- [x] 9.6 `tests/test_batch_processing.py`: POST + process → status=COMPLETED, processed=5, failed=0, hay 5 filas en `prediction_requests` con `source=batch`
- [x] 9.7 Mismo archivo: CSV con filas inválidas → COMPLETED, processed=3, failed=2
- [x] 9.8 Mismo archivo: CSV con todas las filas inválidas → FAILED, processed=0, failed=N
- [x] 9.9 `tests/test_batch_idempotency.py`: invocar `process_job` dos veces sobre el mismo job → segunda corrida no duplica filas. Y CSV con `external_id` repetido → 4 filas, no 5
- [x] 9.10 `tests/test_batch_results.py`: GET `/batch-predictions/{id}/results?limit=2&offset=2` → paginación correcta
- [x] 9.11 GET `/batch-predictions/{id}` con UUID inexistente → 404
- [x] 9.12 Correr suite completa: unit (sin DB) + integration (con DB) — todos verdes

## 10. Documentación

- [x] 10.1 README: sección **"Predicciones batch (CSV)"** con formato del CSV (headers, columnas requeridas/opcionales), ejemplo `curl -F file=@samples/sample_batch.csv localhost:8000/batch-predictions`, polling de estado, descarga de resultados
- [x] 10.2 Mover `tests/fixtures/sample_batch.csv` a `samples/` también, o duplicar — uno para tests, otro como ejemplo público
- [x] 10.3 `docs/decisions.md`: ADR-10 (BackgroundTasks vs worker), ADR-11 (csv stdlib vs pandas), ADR-12 (UNIQUE parcial por `(job_id, external_id)`), ADR-13 (semántica de FAILED). Actualizar lista de "próximas" decisiones
- [x] 10.4 `docs/semana-4.md`: marcar tareas del roadmap
- [x] 10.5 `docs/architecture.md`: confirmar el schema `batch_jobs` matchea la implementación, ajustar si difiere

## 11. Docker

- [x] 11.1 Dockerfile: no requiere cambios (csv stdlib)
- [x] 11.2 `docker compose up -d --build` y smoke test: `curl -F file=@samples/sample_batch.csv :8000/batch-predictions`, luego `curl :8000/batch-predictions/{id}` hasta `COMPLETED`, luego `curl :8000/batch-predictions/{id}/results`

## 12. Cierre

- [ ] 12.1 Commit: `feat(api): batch CSV predictions with job state machine and idempotency`
- [ ] 12.2 Tag `v0.4` (manual)
- [ ] 12.3 Archivar este change con `/opsx:archive`
