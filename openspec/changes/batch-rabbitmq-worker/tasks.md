## 1. Infra y dependencias

- [x] 1.1 Agregar `aio-pika` a `requirements.txt` (pin minor) y reinstalar.
- [x] 1.2 Agregar servicio `rabbitmq` a `docker-compose.yml` (imagen `rabbitmq:3.13-management-alpine`, puertos 5672 y 15672, healthcheck `rabbitmq-diagnostics ping`, env `RABBITMQ_DEFAULT_USER/PASS` desde `.env`, volumen `rabbitmq_data` para persistencia).
- [x] 1.3 Agregar `RABBITMQ_URL`, `RABBITMQ_QUEUE_BATCH`, `BATCH_ORPHAN_THRESHOLD_SECONDS`, `WORKER_PREFETCH_COUNT` a `.env.example` y `app/config.py` (`Settings`).
- [x] 1.4 Agregar servicio `worker` a `docker-compose.yml` (mismo build que `api`, command `python -m app.worker.main`, `depends_on: postgres + rabbitmq healthy`, misma env).

## 2. Migración Alembic

- [x] 2.1 Crear revisión `alembic revision -m "add csv_blob to batch_jobs"` con `csv_blob BYTEA NULL` en `batch_jobs`.
- [x] 2.2 Actualizar `app/db/models.py` (`BatchJob.csv_blob: Mapped[bytes | None]`).
- [x] 2.3 Correr `alembic upgrade head` local y verificar columna.

## 3. Cliente AMQP compartido

- [x] 3.1 Crear `app/queue/__init__.py`.
- [x] 3.2 Crear `app/queue/connection.py` con un wrapper `RabbitConnection` (`aio-pika`) que abre conexión robusta, declara la cola `batch_jobs.process` (durable) idempotentemente, y expone `publish_job(job_id: UUID)`.
- [x] 3.3 Integrar declaración + healthcheck en el `lifespan` de la API: si falla la conexión o la declaración, el startup aborta.

## 4. API: handler refactorizado

- [x] 4.1 En `app/api/routes/batch.py` (`POST /batch-predictions`): leer bytes del upload, validar tamaño/columnas, crear `BatchJob` con `csv_blob=<bytes>` y `status=PENDING` en la MISMA transacción, después publicar a la cola.
- [x] 4.2 Si el publish falla, hacer rollback de la fila y devolver `500`.
- [x] 4.3 Eliminar el uso de `BackgroundTasks` del handler.
- [x] 4.4 Mantener todas las validaciones existentes (`413` tamaño, `422` columnas faltantes/headers inválidos).

## 5. Worker

- [x] 5.1 Crear `app/worker/__init__.py` y `app/worker/main.py` (entrypoint con asyncio event loop, conexión a DB y broker, llamada al recovery, luego consume forever).
- [x] 5.2 Crear `app/worker/processor.py`: extraer la lógica de procesamiento (chunks, persist, transición de estado) que vive hoy en el servicio batch a una función `async def process_job(job_id: UUID)` que lee `csv_blob` de DB, procesa, limpia `csv_blob` al final.
- [x] 5.3 Crear `app/worker/consumer.py`: consumer `aio-pika` con `prefetch_count` desde config, ack manual on success, nack `requeue=True` en errores transitorios (DB caída) y `requeue=False` en errores de datos (CSV malformado, JSON inválido).
- [x] 5.4 Crear `app/worker/recovery.py`: sweep al startup que busca jobs en `PROCESSING` con `started_at < NOW() - threshold` y los republica en la cola, loggeando cada job_id recuperado.
- [x] 5.5 Logging estructurado: cada consumed/acked/nacked/recovered con `job_id`.

## 6. Refactor del servicio batch existente

- [x] 6.1 Mover la lógica de procesamiento desde `app/services/batch_service.py` (o donde viva el BackgroundTask actual) a `app/worker/processor.py` o un módulo `app/services/batch_processor.py` reutilizable por el worker.
- [x] 6.2 Asegurar que la lógica de processed/failed counters y la transición de estado siga idéntica.
- [x] 6.3 Verificar que la lectura del CSV use `csv_blob` (no el upload original), parseando los bytes con `io.BytesIO`.

## 7. Tests

- [x] 7.1 Agregar marca `worker` en `pyproject.toml`/`pytest.ini` y documentar en README.
- [x] 7.2 Crear `tests/conftest.py` fixture `rabbitmq_channel` que se conecta al broker del compose y purga la cola entre tests.
- [x] 7.3 Actualizar tests existentes de `POST /batch-predictions`: ya no esperan procesamiento sincrónico, validan que (a) se creó el `BatchJob` con `csv_blob`, (b) se publicó un mensaje a la cola, (c) la response es `202`.
- [x] 7.4 Nuevo test `tests/worker/test_processor.py` (marca `worker`): end-to-end — publica un job_id, espera (con timeout) a que el worker consuma y transicione el job a `COMPLETED`, verifica filas en `prediction_requests`.
- [x] 7.5 Nuevo test de recovery: insertar un `BatchJob` en `PROCESSING` con `started_at` antiguo, arrancar el worker (programáticamente o vía función `run_recovery`), verificar que se publicó un mensaje y se proceso el job.
- [x] 7.6 Nuevo test de idempotency bajo redelivery: publicar dos veces el mismo `job_id` para un CSV con `external_id`s, verificar que no se duplican filas en `prediction_requests`.
- [x] 7.7 Nuevo test de transient failure: simular DB caída durante el procesamiento, verificar que el mensaje se requeue y que un segundo intento (DB up) completa el job.
- [x] 7.8 Nuevo test de poison message: publicar un `job_id` cuyo `csv_blob` es inválido, verificar que se nack-ea sin requeue y el job termina en `FAILED`.

## 8. Docs y wrap-up

- [x] 8.1 Actualizar `README.md` sección Docker: ahora `docker compose up` levanta `postgres`, `rabbitmq`, `api`, `worker`. Documentar UI de RabbitMQ en `:15672`.
- [x] 8.2 Actualizar `README.md` sección Tests: nueva marca `worker`, requiere `rabbitmq` corriendo.
- [x] 8.3 Actualizar `README.md` sección Predicciones batch: explicar el nuevo flujo (publish → worker → status polling) en una línea, sin cambiar los ejemplos de `curl`.
- [x] 8.4 Agregar `docs/decisions.md` ADR-lite: "Por qué RabbitMQ + aio-pika para batch" (resumen de design.md).
- [x] 8.5 Crear `docs/semana-5.md` con un resumen breve del sprint (qué se construyó, cómo testearlo localmente).
- [x] 8.6 Verificar `openspec validate batch-rabbitmq-worker` pasa.
- [ ] 8.7 Tag `v0.5` después del merge a main.
