## ADDED Requirements

### Requirement: Broker connectivity at startup
The worker process SHALL validar conectividad con RabbitMQ al startup, abriendo una conexión AMQP y declarando la cola de trabajo antes de empezar a consumir. Si la conexión falla, el proceso MUST abortar el startup con error explícito; NO SE PERMITE quedar idle con broker caído.

La API SHALL también declarar (idempotente) la cola `batch_jobs.process` al startup. Si la declaración falla, el startup de la API MUST abortar.

#### Scenario: Worker aborts when broker is unreachable
- **WHEN** el worker intenta arrancar y `RABBITMQ_URL` apunta a un host inaccesible
- **THEN** el startup falla propagando la excepción y el proceso termina con exit code distinto de 0

#### Scenario: API aborts when broker is unreachable
- **WHEN** la API intenta arrancar y la conexión a RabbitMQ falla
- **THEN** el startup falla y el servicio NO queda escuchando

#### Scenario: Queue is declared idempotently
- **GIVEN** la cola `batch_jobs.process` ya existe en el broker
- **WHEN** la API o el worker arrancan y declaran la cola
- **THEN** la declaración no falla y la cola conserva sus propiedades existentes

### Requirement: Durable work queue
The system SHALL usar una cola RabbitMQ llamada `batch_jobs.process` (nombre configurable vía `RABBITMQ_QUEUE_BATCH`) declarada con `durable=True`. Los mensajes publicados MUST tener `delivery_mode=2` (persistent). Cada mensaje MUST contener un payload JSON con al menos el campo `job_id` (UUID v4 como string).

#### Scenario: Queue survives broker restart
- **GIVEN** hay mensajes pendientes en la cola
- **WHEN** RabbitMQ se reinicia
- **THEN** la cola y sus mensajes pendientes siguen presentes al reanudar

#### Scenario: Published message contains job_id
- **WHEN** la API publica un mensaje para un job recién creado
- **THEN** el mensaje contiene exactamente `{"job_id": "<uuid>"}` y se publica como persistent

### Requirement: Manual ack with requeue policy
The worker SHALL consumir la cola con acks manuales (`auto_ack=False`). El mensaje MUST ser `ack`-eado únicamente después de que el job haya transicionado a estado final (`COMPLETED` o `FAILED`) en `batch_jobs`. En caso de excepción durante el procesamiento, el worker MUST hacer `nack` con `requeue=True` para errores transitorios (DB caída, timeout) o `nack` con `requeue=False` para errores de datos no recuperables (CSV malformado, columnas faltantes en el blob persistido).

#### Scenario: Successful processing acks the message
- **WHEN** el worker termina un job exitosamente y actualiza `batch_jobs.status = COMPLETED`
- **THEN** el mensaje se ack-ea y desaparece de la cola

#### Scenario: Transient failure requeues the message
- **WHEN** el worker está procesando un job y la DB cae
- **THEN** el mensaje se nack-ea con `requeue=True` y vuelve a la cola para otro intento

#### Scenario: Worker crashes mid-processing
- **GIVEN** un worker consumió un mensaje pero crashea antes de ack
- **WHEN** el broker detecta la pérdida de la conexión
- **THEN** el mensaje vuelve a quedar disponible (RabbitMQ lo redelivera al próximo consumer)

### Requirement: Bounded prefetch
The worker SHALL configurar `prefetch_count` (default `1`, configurable vía `WORKER_PREFETCH_COUNT`) para limitar cuántos mensajes reserva en paralelo. Esto evita que un solo consumer tome muchos mensajes y los pierda todos si crashea.

#### Scenario: Prefetch limits in-flight messages
- **GIVEN** `WORKER_PREFETCH_COUNT=1` y dos mensajes en la cola
- **WHEN** un solo worker está corriendo
- **THEN** el worker tiene exactamente 1 mensaje unacked a la vez

### Requirement: CSV payload persisted with the job
The system SHALL guardar el contenido crudo del CSV en la columna `batch_jobs.csv_blob` (`BYTEA NULL`) en el momento en que la API crea el job. El worker SHALL leer `csv_blob` por `job_id` para procesar el archivo. Al transicionar el job a estado final (`COMPLETED` o `FAILED`), el worker MUST limpiar la columna (`UPDATE batch_jobs SET csv_blob = NULL`) para acotar el crecimiento de la tabla.

#### Scenario: CSV blob is written on submission
- **WHEN** la API procesa un `POST /batch-predictions` válido
- **THEN** la fila en `batch_jobs` contiene `csv_blob` con los bytes exactos del archivo subido

#### Scenario: CSV blob is cleared after completion
- **GIVEN** un job que transicionó a `COMPLETED`
- **WHEN** el worker termina de procesarlo
- **THEN** la fila correspondiente tiene `csv_blob IS NULL`

#### Scenario: CSV blob is cleared after failure
- **GIVEN** un job que transicionó a `FAILED`
- **WHEN** el worker termina de procesarlo
- **THEN** la fila correspondiente tiene `csv_blob IS NULL`

### Requirement: Orphan job recovery at worker startup
The worker SHALL ejecutar, al startup y antes de empezar a consumir la cola, un sweep que detecta jobs huérfanos: filas en `batch_jobs` con `status = 'PROCESSING'` cuyo `started_at` es más antiguo que `BATCH_ORPHAN_THRESHOLD_SECONDS` (default 600). Por cada job huérfano detectado, el worker MUST publicar de nuevo un mensaje en la cola con `{"job_id": <id>}`. La idempotencia preexistente por `external_id` evita duplicados en `prediction_requests` para filas que lo declaren.

#### Scenario: Orphan job is requeued
- **GIVEN** existe una fila en `batch_jobs` con `status = 'PROCESSING'` y `started_at` hace 30 minutos
- **AND** `BATCH_ORPHAN_THRESHOLD_SECONDS = 600`
- **WHEN** el worker arranca
- **THEN** se publica un mensaje con ese `job_id` en `batch_jobs.process` y el sweep loggea el job_id recuperado

#### Scenario: Recent job is not considered orphan
- **GIVEN** existe una fila en `batch_jobs` con `status = 'PROCESSING'` y `started_at` hace 60 segundos
- **AND** `BATCH_ORPHAN_THRESHOLD_SECONDS = 600`
- **WHEN** el worker arranca
- **THEN** ese job NO se republica

#### Scenario: PENDING and final-state jobs are not recovered
- **GIVEN** existen filas en `batch_jobs` con `status ∈ {PENDING, COMPLETED, FAILED}`
- **WHEN** el worker arranca
- **THEN** ninguna de esas filas se republica

### Requirement: Worker processes the same logic as the previous in-process batch
The worker, al consumir un mensaje, SHALL ejecutar la misma lógica de procesamiento que antes vivía en `BackgroundTasks`: transición `PENDING → PROCESSING`, lectura del CSV (desde `csv_blob`), procesamiento en chunks (`BATCH_CHUNK_SIZE`, default 1000), persistencia de cada predicción con `source = "batch"`, incremento de `processed`/`failed` por fila, y transición final a `COMPLETED` (si `processed > 0`) o `FAILED` (si `processed == 0` con `total_records > 0`).

#### Scenario: Worker preserves end-to-end semantics
- **GIVEN** un CSV con 5 filas válidas subido vía `POST /batch-predictions`
- **WHEN** el worker procesa el mensaje correspondiente
- **THEN** existen 5 filas en `prediction_requests` con `source = "batch"` y `job_id` igual, y `batch_jobs.status = COMPLETED` con `processed = 5`, `failed = 0`

#### Scenario: Worker preserves row-level tolerance
- **GIVEN** un CSV con 5 filas (2 inválidas) procesado por el worker
- **THEN** `batch_jobs.status = COMPLETED`, `processed = 3`, `failed = 2`, y `prediction_requests` tiene 3 filas para ese `job_id`

#### Scenario: Worker preserves idempotency per external_id
- **GIVEN** un mensaje para un `job_id` se entrega dos veces al worker (por requeue o por recovery)
- **AND** todas las filas del CSV tienen `external_id`
- **THEN** el total de filas en `prediction_requests` para ese `job_id` permanece igual al número de `external_id` únicos del CSV
