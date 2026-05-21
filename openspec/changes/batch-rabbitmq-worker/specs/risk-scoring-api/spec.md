## MODIFIED Requirements

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
