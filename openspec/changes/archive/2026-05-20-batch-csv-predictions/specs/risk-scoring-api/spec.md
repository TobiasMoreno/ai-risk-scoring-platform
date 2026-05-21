## MODIFIED Requirements

### Requirement: Risk scoring (ML model)
The system SHALL exponer `POST /risk-score` que acepta un payload JSON con los campos `income` (float > 0), `age` (int, 18–100 inclusive), `debt` (float ≥ 0) y `employment_years` (int ≥ 0), y devuelve un `RiskScoreResponse` con `request_id` (UUID v4 generado en servidor), `risk_score` (float en [0, 1]), `risk_level` (uno de `"low" | "medium" | "high"`) y `model_version` (string).

El cálculo MUST provenir del modelo Scikit-learn cargado al startup. El servicio MUST persistir el resultado en la tabla `prediction_requests` antes de devolver la response con `source = "online"`, `job_id = NULL` y `external_id = NULL`. Si la persistencia falla, la API MUST responder `500 Internal Server Error` y NO devolver predicción.

#### Scenario: Online path persists with source=online
- **WHEN** se envía un payload válido a `POST /risk-score`
- **THEN** el servicio responde `200 OK` y crea una fila en `prediction_requests` con `source = "online"`, `job_id = NULL`, `external_id = NULL`

#### Scenario: Database failure does not return a prediction
- **WHEN** la persistencia falla
- **THEN** el servicio responde `500 Internal Server Error` y NO devuelve `risk_score`

#### Scenario: Invalid input is rejected
- **WHEN** se envía un payload donde `income <= 0`, `age < 18`, `age > 100`, `debt < 0` o `employment_years < 0`
- **THEN** el servicio responde `422 Unprocessable Entity` y NO se invoca al modelo ni se escribe en DB

#### Scenario: Missing field is rejected
- **WHEN** se envía un payload al que le falta cualquiera de los cuatro campos requeridos
- **THEN** el servicio responde `422 Unprocessable Entity`

## ADDED Requirements

### Requirement: Batch prediction submission
The system SHALL exponer `POST /batch-predictions` que acepta un upload multipart/form-data con un archivo CSV en el campo `file`. El CSV MUST contener al menos las columnas `income`, `age`, `debt`, `employment_years`; la columna `external_id` es opcional. El servicio MUST crear una fila en `batch_jobs` con `status = "PENDING"`, `total_records` = número de filas de datos en el CSV, `processed = 0`, `failed = 0`, y devolver `202 Accepted` con `{job_id, status, total_records}` y header `Location: /batch-predictions/{job_id}`. El procesamiento MUST iniciarse de forma asincrónica (vía `BackgroundTasks` o equivalente) tras devolver la response.

Si el archivo excede el tamaño máximo configurado (default 10 MB), el servicio MUST responder `413 Payload Too Large` sin crear el job. Si faltan columnas requeridas en el header del CSV, MUST responder `422 Unprocessable Entity`.

#### Scenario: Valid CSV creates a PENDING job
- **WHEN** se sube un CSV válido con 5 filas a `POST /batch-predictions`
- **THEN** el servicio responde `202 Accepted` con `status = "PENDING"`, `total_records = 5`, `job_id` UUID válido y header `Location: /batch-predictions/{job_id}`
- **AND** existe una fila correspondiente en `batch_jobs`

#### Scenario: Missing required columns is rejected
- **WHEN** se sube un CSV cuyo header NO incluye `income`, `age`, `debt` o `employment_years`
- **THEN** el servicio responde `422 Unprocessable Entity` y NO se crea ninguna fila en `batch_jobs`

#### Scenario: Oversized upload is rejected
- **WHEN** se sube un archivo cuyo tamaño excede `batch_max_upload_bytes`
- **THEN** el servicio responde `413 Payload Too Large` y NO se crea ninguna fila en `batch_jobs`

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
