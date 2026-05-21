## Why

Hoy el procesamiento batch corre dentro del proceso de la API vía `BackgroundTasks` de FastAPI: si el contenedor de la API se reinicia mid-job, el trabajo queda huérfano (`status` colgado en `PROCESSING`) y nadie lo reanuda. Esto también acopla la latencia y memoria del path online con cargas batch arbitrariamente grandes, y no escala horizontalmente (no se pueden agregar workers sin replicar también la API). S5 de la ruta de estudio apunta justamente a aprender cola + worker desacoplados como una pieza típica de plataforma ML.

## What Changes

- Introducir **RabbitMQ** como broker en `docker-compose.yml` (servicio `rabbitmq`, imagen oficial con management plugin, puerto AMQP 5672 + UI 15672, credenciales vía `.env`).
- Reemplazar `BackgroundTasks` en `POST /batch-predictions` por un **publish** a una cola durable `batch_jobs.process` con un mensaje `{job_id}`. El handler HTTP NO procesa nada del CSV: solo valida headers/tamaño, crea la fila en `batch_jobs` (`status=PENDING`) y publica.
- Nuevo proceso **worker** independiente (`app/worker/main.py`) que consume la cola con prefetch limitado, acks manuales, requeue en error, y ejecuta la lógica de procesamiento que hoy vive en `BackgroundTasks` (chunks, persistencia, transición de estado).
- Nuevo servicio `worker` en `docker-compose.yml` (misma imagen que `api`, comando distinto: `python -m app.worker.main`).
- Recuperación de jobs huérfanos: al startup, el worker hace un sweep de `batch_jobs` en estado `PROCESSING` con `started_at` más viejo que un threshold configurable (`BATCH_ORPHAN_THRESHOLD_SECONDS`, default 600s) y los re-publica en la cola (idempotencia preexistente por `external_id` evita duplicados).
- Tests: nueva marca `pytest -m worker` (integración real contra RabbitMQ del compose). Los tests existentes de `POST /batch-predictions` se actualizan: ya no esperan procesamiento sincrónico in-process, solo que se haya publicado.
- **BREAKING (interno)**: cualquier caller que dependiera de que el job pasara a `COMPLETED` dentro del mismo proceso queda invalidado. El contrato HTTP público (`202` + polling de `GET /batch-predictions/{job_id}`) **no cambia**.
- Bump de tag a `v0.5`.

## Capabilities

### New Capabilities
- `batch-job-queue`: cola durable + worker para procesar jobs batch fuera del proceso API, con recuperación de jobs huérfanos al startup del worker.

### Modified Capabilities
- `risk-scoring-api`: el requirement "Batch prediction submission" deja de procesar in-process; el endpoint solo encola. La state machine y los demás endpoints (`GET /batch-predictions/{id}`, `/results`) no cambian su contrato observable, pero la transición `PENDING → PROCESSING` ahora la hace el worker, no la API.

## Impact

- **Código**: `app/services/batch_service.py` (extraer la lógica de procesamiento para que la consuma el worker), `app/api/routes/batch.py` (reemplazar `BackgroundTasks` por publish), nuevo `app/worker/` (entrypoint + consumer + recovery), nuevo `app/queue/` (cliente AMQP wrapper, conexión, declaración de cola).
- **Infra**: `docker-compose.yml` gana `rabbitmq` y `worker`; `Dockerfile` no cambia (la imagen ya tiene todo lo necesario).
- **Config**: nuevas env vars `RABBITMQ_URL`, `RABBITMQ_QUEUE_BATCH`, `BATCH_ORPHAN_THRESHOLD_SECONDS`, `WORKER_PREFETCH_COUNT`. Documentar en `.env.example`.
- **Dependencias**: agregar `aio-pika` a `requirements.txt`.
- **Docs**: actualizar `README.md` (sección Docker, ahora `docker compose up` levanta también `rabbitmq` y `worker`); nuevo `docs/semana-5.md` (queda fuera del scope técnico pero referenciado).
- **Tests**: nueva fixture para conexión a RabbitMQ; nueva marca `worker` en `pyproject.toml` o `pytest.ini`.
- **No afecta**: el path online (`POST /risk-score`), `GET /predictions/*`, `/metrics/summary`, `/health`.
