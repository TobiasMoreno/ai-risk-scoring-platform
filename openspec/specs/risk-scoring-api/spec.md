# risk-scoring-api Specification

## Purpose
Provides a FastAPI HTTP service that exposes risk scoring functionality for consumer financial profiles. The service uses a Scikit-learn pipeline (`StandardScaler → LogisticRegression`) trained offline and loaded once at startup to produce probability-based risk scores. Every prediction is persisted in PostgreSQL (table `prediction_requests`, backed by `TIMESTAMPTZ` `created_at`), and the service exposes lookup, listing and summary endpoints over that store. The previous mock implementation is historic and has been replaced by this ML- and DB-backed version, while preserving the public contract (endpoints, schemas, error semantics).
## Requirements
### Requirement: Health endpoint
The system SHALL expose `GET /health` that returns HTTP 200 with body `{"status": "ok"}` siempre que el proceso esté vivo. No depende de recursos externos.

#### Scenario: Health check responds OK
- **WHEN** un cliente hace `GET /health`
- **THEN** el servicio responde `200 OK` con `Content-Type: application/json` y body exactamente `{"status": "ok"}`

### Requirement: Risk scoring (ML model)
The system SHALL exponer `POST /risk-score` que acepta un payload JSON con los campos `income` (float > 0), `age` (int, 18–100 inclusive), `debt` (float ≥ 0) y `employment_years` (int ≥ 0), y devuelve un `RiskScoreResponse` con `request_id` (UUID v4 generado en servidor), `risk_score` (float en [0, 1]), `risk_level` (uno de `"low" | "medium" | "high"`) y `model_version` (string).

El cálculo MUST provenir del modelo Scikit-learn cargado al startup (pipeline `StandardScaler → LogisticRegression`). El servicio MUST persistir el resultado en la tabla `prediction_requests` antes de devolver la response con `source = "online"`, `job_id = NULL` y `external_id = NULL`. Si la persistencia falla, la API MUST responder `500 Internal Server Error` y NO devolver predicción. La response NO incluye `latency_ms`; ese valor se guarda en DB.

El registro persistido MUST incluir como mínimo: `request_id`, `input_payload` (JSON con los 4 campos), `prediction` (JSON con `risk_score`, `risk_level`, `model_version`), `model_version`, `latency_ms` (entero, milisegundos), `source` (`"online"` para esta ruta) y `created_at` (timestamp servidor).

#### Scenario: Online path persists with source=online
- **WHEN** se envía un payload válido a `POST /risk-score`
- **THEN** el servicio responde `200 OK` y crea una fila en `prediction_requests` con `source = "online"`, `job_id = NULL`, `external_id = NULL`

#### Scenario: Happy path persists and returns the score
- **WHEN** se envía un payload válido a `POST /risk-score`
- **THEN** el servicio responde `200 OK` con `risk_score ∈ [0, 1]`, `risk_level` consistente con los umbrales 0.33 / 0.66, `model_version` igual al configurado, y un `request_id` UUID válido
- **AND** existe una nueva fila en `prediction_requests` con `request_id` igual al de la response, `source = "online"`, `latency_ms ≥ 0` y `created_at` reciente

#### Scenario: Database failure does not return a prediction
- **WHEN** la persistencia falla (DB caída, restricción violada, error inesperado en `repo.save()`)
- **THEN** el servicio responde `500 Internal Server Error` y NO se devuelve un body con `risk_score`

#### Scenario: Invalid input is rejected
- **WHEN** se envía un payload donde `income <= 0`, `age < 18`, `age > 100`, `debt < 0` o `employment_years < 0`
- **THEN** el servicio responde `422 Unprocessable Entity` y NO se invoca al modelo ni se escribe en DB

#### Scenario: Missing field is rejected
- **WHEN** se envía un payload al que le falta cualquiera de los cuatro campos requeridos
- **THEN** el servicio responde `422 Unprocessable Entity`

### Requirement: Batch prediction submission
The system SHALL exponer `POST /batch-predictions` que acepta un upload multipart/form-data con un archivo CSV en el campo `file`. El CSV MUST contener al menos las columnas `income`, `age`, `debt`, `employment_years`; la columna `external_id` es opcional. El servicio MUST crear una fila en `batch_jobs` con `status = "PENDING"`, `total_records` = número de filas de datos en el CSV, `processed = 0`, `failed = 0`, persistir los bytes crudos del CSV en `batch_jobs.csv_blob`, y publicar un mensaje `{"job_id": <id>}` en la cola RabbitMQ `batch_jobs.process` (durable, mensaje persistent). La response MUST ser `202 Accepted` con `{job_id, status, total_records}` y header `Location: /batch-predictions/{job_id}`. El handler HTTP NO MUST ejecutar ninguna lógica de procesamiento del CSV más allá de la validación del header y el conteo de filas; el procesamiento ocurre asincrónicamente en un worker independiente.

Si el archivo excede el tamaño máximo configurado (default 10 MB), el servicio MUST responder `413 Payload Too Large` sin crear el job ni publicar mensaje. Si faltan columnas requeridas en el header del CSV, MUST responder `422 Unprocessable Entity`. Si la publicación a la cola falla, el servicio MUST responder `500 Internal Server Error` y NO crear el job (transaccional: o se crea la fila + se publica el mensaje, o nada).

#### Scenario: Valid CSV creates a PENDING job and enqueues a message
- **WHEN** se sube un CSV válido con 5 filas a `POST /batch-predictions`
- **THEN** el servicio responde `202 Accepted` con `status = "PENDING"`, `total_records = 5`, `job_id` UUID válido y header `Location: /batch-predictions/{job_id}`
- **AND** existe una fila correspondiente en `batch_jobs` con `csv_blob` no nulo
- **AND** existe un mensaje en la cola `batch_jobs.process` con `{"job_id": "<el mismo>"}` (o ya fue consumido por el worker)

#### Scenario: Missing required columns is rejected
- **WHEN** se sube un CSV cuyo header NO incluye `income`, `age`, `debt` o `employment_years`
- **THEN** el servicio responde `422 Unprocessable Entity` y NO se crea ninguna fila en `batch_jobs` ni se publica mensaje

#### Scenario: Oversized upload is rejected
- **WHEN** se sube un archivo cuyo tamaño excede `batch_max_upload_bytes`
- **THEN** el servicio responde `413 Payload Too Large` y NO se crea ninguna fila en `batch_jobs` ni se publica mensaje

#### Scenario: Broker publish failure does not leak a job
- **WHEN** la publicación a RabbitMQ falla después de la validación del CSV
- **THEN** el servicio responde `500 Internal Server Error` y NO existe ninguna fila en `batch_jobs` para esa submission

#### Scenario: Handler does not perform processing
- **WHEN** se sube un CSV válido y se inspecciona la respuesta HTTP inmediatamente
- **THEN** la respuesta vuelve sin haber escrito ninguna fila en `prediction_requests` (el procesamiento es responsabilidad del worker)

### Requirement: Batch job status lookup
The system SHALL exponer `GET /batch-predictions/{job_id}` donde `job_id` MUST ser un UUID válido. Devuelve `200 OK` con el estado completo del job (`job_id`, `status`, `total_records`, `processed`, `failed`, `started_at`, `finished_at`, `created_at`) o `404 Not Found` si no existe.

El campo `status` MUST ser uno de: `"PENDING"`, `"PROCESSING"`, `"COMPLETED"`, `"FAILED"`. La transición canónica es `PENDING → PROCESSING → (COMPLETED | FAILED)`. `FAILED` se reserva para casos donde ninguna fila se persistió exitosamente (`processed == 0` y `total_records > 0`); si al menos una fila se persistió, el estado final MUST ser `COMPLETED`.

#### Scenario: Returns current status
- **GIVEN** un `job_id` existente
- **WHEN** un cliente hace `GET /batch-predictions/{job_id}`
- **THEN** el servicio responde `200 OK` con `status`, `total_records`, `processed`, `failed`, y timestamps consistentes con el estado

#### Scenario: Not found
- **WHEN** un cliente hace `GET /batch-predictions/{job_id}` con un UUID que no existe
- **THEN** el servicio responde `404 Not Found`

#### Scenario: Invalid UUID is rejected
- **WHEN** un cliente hace `GET /batch-predictions/no-es-un-uuid`
- **THEN** el servicio responde `422 Unprocessable Entity`

### Requirement: Batch job results listing
The system SHALL exponer `GET /batch-predictions/{job_id}/results?limit=<N>&offset=<M>` que devuelve las predicciones persistidas para ese job, ordenadas por `created_at ASC` (orden de procesamiento). Defaults: `limit=50`, `offset=0`. `limit` MUST estar en `[1, 200]`. `offset` MUST ser `≥ 0`. Si el job no existe, MUST responder `404 Not Found`.

Cada elemento de la respuesta MUST tener el mismo shape que `GET /predictions/{request_id}` (`request_id`, `input_payload`, `prediction`, `model_version`, `latency_ms`, `source = "batch"`, `created_at`) más opcionalmente `external_id`.

#### Scenario: Returns persisted predictions for the job
- **GIVEN** un job COMPLETED con 5 predicciones
- **WHEN** un cliente hace `GET /batch-predictions/{job_id}/results?limit=10`
- **THEN** el servicio responde `200 OK` con un array de 5 elementos, todos con `source = "batch"`

#### Scenario: Pagination
- **GIVEN** un job COMPLETED con 5 predicciones
- **WHEN** un cliente hace `GET /batch-predictions/{job_id}/results?limit=2&offset=2`
- **THEN** el servicio devuelve los elementos 3 y 4

#### Scenario: Unknown job
- **WHEN** un cliente hace `GET /batch-predictions/{job_id}/results` con un job inexistente
- **THEN** el servicio responde `404 Not Found`

### Requirement: Batch idempotency per external_id
Para filas que incluyen `external_id`, el sistema MUST garantizar que dentro de un mismo `job_id` no se persistan dos filas con el mismo `external_id`. Reintentar el procesamiento del mismo CSV bajo el mismo `job_id` MUST resultar en cero inserts duplicados; las filas re-vistas se cuentan como "ya procesadas" (no incrementan `failed`). Filas sin `external_id` quedan fuera de esta garantía.

#### Scenario: Reprocessing the same CSV does not duplicate
- **GIVEN** un CSV con 5 filas con `external_id` distintos, procesado completamente
- **WHEN** se vuelve a invocar el procesamiento del mismo `job_id` (idealmente por reintento del servicio, no por nueva subida)
- **THEN** la cantidad total de filas en `prediction_requests` con ese `job_id` permanece en 5

#### Scenario: Duplicate external_id within a job is skipped
- **GIVEN** un CSV con 5 filas donde dos comparten `external_id`
- **WHEN** el job termina
- **THEN** `prediction_requests` contiene 4 filas para ese `job_id` (la duplicada se omite), y `failed` NO se incrementa por la duplicada

### Requirement: Batch row validation tolerance
Filas individuales con datos inválidos (violan las reglas de validación de `RiskScoreRequest`) MUST incrementar el contador `failed` del job y registrarse en el log con el número de línea, sin abortar el procesamiento del resto del archivo.

#### Scenario: Invalid rows do not break the job
- **GIVEN** un CSV con 5 filas, donde 2 tienen valores inválidos (ej. `income = 0` o falta `age`)
- **WHEN** el job termina
- **THEN** `status = "COMPLETED"`, `processed = 3`, `failed = 2`, y existen exactamente 3 filas en `prediction_requests` para ese `job_id`

### Requirement: OpenAPI documentation
The system SHALL publicar la documentación OpenAPI generada por FastAPI en `/docs` (Swagger UI) y `/openapi.json`, reflejando los schemas Pydantic de request y response.

#### Scenario: Docs are reachable
- **WHEN** un cliente hace `GET /docs`
- **THEN** el servicio responde `200 OK` con HTML de Swagger UI listando los tres endpoints (`/health`, `/risk-score`, `/predictions/{id}`)

### Requirement: Model loading at startup
The system SHALL cargar el modelo serializado (`app/models/risk_model.joblib` por defecto, configurable vía `Settings.model_path` / `MODEL_PATH`) durante el `lifespan` de la aplicación, antes de aceptar requests. Si la carga falla (archivo ausente, archivo corrupto, incompatibilidad de versión de scikit-learn), el proceso MUST abortar el startup con un error explícito; NO SE PERMITE servir requests con un modelo no cargado.

#### Scenario: Missing model file aborts startup
- **WHEN** la aplicación intenta arrancar y `Settings.model_path` apunta a un archivo inexistente
- **THEN** el startup falla con una excepción que identifica el path buscado, y el servicio NO queda escuchando

#### Scenario: Corrupt model file aborts startup
- **WHEN** la aplicación intenta arrancar y `joblib.load(Settings.model_path)` lanza una excepción
- **THEN** el startup falla propagando la excepción original, y el servicio NO queda escuchando

#### Scenario: Successful load is logged
- **WHEN** la aplicación arranca con un modelo válido
- **THEN** el log incluye un mensaje con `model_version` y `model_path` confirmando la carga, antes de que el servidor empiece a aceptar requests

### Requirement: Prediction lookup by request_id
The system SHALL exponer `GET /predictions/{request_id}` donde `request_id` MUST ser un UUID válido. Devuelve `200 OK` con el registro persistido (request_id, input_payload, prediction, model_version, latency_ms, source, created_at) o `404 Not Found` si no existe.

#### Scenario: Returns the persisted prediction
- **GIVEN** un `request_id` que existe en `prediction_requests`
- **WHEN** un cliente hace `GET /predictions/{request_id}`
- **THEN** el servicio responde `200 OK` con `request_id`, `input_payload`, `prediction`, `model_version`, `latency_ms`, `source`, `created_at`

#### Scenario: Not found returns 404
- **WHEN** un cliente hace `GET /predictions/{request_id}` con un UUID que no existe
- **THEN** el servicio responde `404 Not Found` con un body que incluye `detail`

#### Scenario: Invalid UUID returns 422
- **WHEN** un cliente hace `GET /predictions/no-es-un-uuid`
- **THEN** el servicio responde `422 Unprocessable Entity`

### Requirement: Recent predictions listing
The system SHALL exponer `GET /predictions?limit=<N>&offset=<M>` que devuelve la lista de predicciones ordenadas por `created_at DESC`. Default: `limit=50`, `offset=0`. `limit` MUST ser entero en `[1, 200]`. `offset` MUST ser entero `≥ 0`.

#### Scenario: Returns recent predictions in descending order
- **GIVEN** existen al menos 3 predicciones persistidas
- **WHEN** un cliente hace `GET /predictions?limit=2`
- **THEN** el servicio responde `200 OK` con un array de 2 elementos, ordenados por `created_at` descendente

#### Scenario: Pagination via offset
- **GIVEN** existen al menos 5 predicciones persistidas
- **WHEN** un cliente hace `GET /predictions?limit=2&offset=2`
- **THEN** el servicio devuelve los elementos 3 y 4 (1-indexed desde el más reciente)

#### Scenario: limit out of range is rejected
- **WHEN** un cliente hace `GET /predictions?limit=500`
- **THEN** el servicio responde `422 Unprocessable Entity`

### Requirement: Predictions summary metrics
The system SHALL exponer `GET /metrics/summary` que devuelve agregados sobre `prediction_requests`. La respuesta MUST incluir: `total` (int), `avg_latency_ms` (float â‰¥ 0), `p95_latency_ms` (float â‰¥ 0), `by_risk_level` (objeto `{low: int, medium: int, high: int}`) y `by_model_version` (objeto `{<model_version>: int, ...}`).

The system SHALL also expose `GET /metrics` in Prometheus text exposition format. The response MUST include runtime metrics such as HTTP request counts/latency, prediction totals, model inference latency, prediction errors, batch job totals, and batch job duration. This endpoint MUST return a Prometheus-compatible content type.

#### Scenario: Returns aggregates over persisted predictions
- **GIVEN** existen predicciones persistidas con varios `model_version` y `risk_level`
- **WHEN** un cliente hace `GET /metrics/summary`
- **THEN** el servicio responde `200 OK` y `total` coincide con `COUNT(*)`, `avg_latency_ms` con el promedio, `by_risk_level` cubre los 3 buckets (cero si no hay registros) y `by_model_version` enumera todas las versiones presentes

#### Scenario: Empty table returns zeros
- **GIVEN** la tabla `prediction_requests` estÃ¡ vacÃ­a
- **WHEN** un cliente hace `GET /metrics/summary`
- **THEN** el servicio responde `200 OK` con `total = 0`, `avg_latency_ms = 0`, `p95_latency_ms = 0`, `by_risk_level = {low: 0, medium: 0, high: 0}`, `by_model_version = {}`

#### Scenario: Prometheus metrics are exposed
- **WHEN** un cliente hace `GET /metrics`
- **THEN** el servicio responde `200 OK` con formato Prometheus e incluye series `risk_predictions_total`, `risk_prediction_latency_seconds`, `risk_prediction_errors_total`, `risk_batch_jobs_total`, `risk_batch_job_duration_seconds`, y `risk_model_inference_latency_seconds`

### Requirement: Database connectivity at startup
The system SHALL validar la conectividad a PostgreSQL durante el `lifespan` de la aplicación, ejecutando `SELECT 1` antes de aceptar requests. Si la conexión falla, el startup MUST abortar con error explícito; NO SE PERMITE servir requests con DB caída.

#### Scenario: Missing or unreachable database aborts startup
- **WHEN** la aplicación intenta arrancar y `DATABASE_URL` apunta a un host inaccesible o credenciales inválidas
- **THEN** el startup falla propagando la excepción, y el servicio NO queda escuchando

#### Scenario: Successful connection is logged
- **WHEN** la aplicación arranca con DB accesible
- **THEN** el log incluye un mensaje confirmando la conexión y el `pool_size` configurado, antes de aceptar requests

### Requirement: Request correlation
The system SHALL assign a request correlation ID to every HTTP request. If the client sends `X-Request-ID`, the API MUST use that value; otherwise it MUST generate a UUID. The response MUST include the effective `X-Request-ID` header, and request logs MUST include the same value.

#### Scenario: Existing request ID is propagated
- **WHEN** a client sends `X-Request-ID: custom-id` to any API endpoint
- **THEN** the response includes `X-Request-ID: custom-id`

#### Scenario: Missing request ID is generated
- **WHEN** a client sends a request without `X-Request-ID`
- **THEN** the response includes a generated `X-Request-ID` value

