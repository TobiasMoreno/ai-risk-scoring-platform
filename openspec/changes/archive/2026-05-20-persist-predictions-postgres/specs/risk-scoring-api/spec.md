## MODIFIED Requirements

### Requirement: Risk scoring (ML model)
The system SHALL exponer `POST /risk-score` que acepta un payload JSON con los campos `income` (float > 0), `age` (int, 18–100 inclusive), `debt` (float ≥ 0) y `employment_years` (int ≥ 0), y devuelve un `RiskScoreResponse` con `request_id` (UUID v4 generado en servidor), `risk_score` (float en [0, 1]), `risk_level` (uno de `"low" | "medium" | "high"`) y `model_version` (string).

El cálculo MUST provenir del modelo Scikit-learn cargado al startup (pipeline `StandardScaler → LogisticRegression`). El servicio MUST persistir el resultado en la tabla `prediction_requests` antes de devolver la response: si la persistencia falla, la API MUST responder `500 Internal Server Error` y NO devolver predicción. La response NO incluye `latency_ms`; ese valor se guarda en DB.

El registro persistido MUST incluir como mínimo: `request_id`, `input_payload` (JSON con los 4 campos), `prediction` (JSON con `risk_score`, `risk_level`, `model_version`), `model_version`, `latency_ms` (entero, milisegundos), `source` (`"online"` para esta ruta) y `created_at` (timestamp servidor).

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

## REMOVED Requirements

### Requirement: Prediction lookup placeholder
**Reason**: La capacidad de lookup ya está implementada contra la tabla `prediction_requests`; el placeholder 501 deja de tener sentido.
**Migration**: Los clientes que hacían `GET /predictions/{id}` recibían `501`; a partir de v0.3 reciben `200` con el registro persistido o `404` si no existe. Ver "Prediction lookup by request_id".

## ADDED Requirements

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
The system SHALL exponer `GET /metrics/summary` que devuelve agregados sobre `prediction_requests`. La respuesta MUST incluir: `total` (int), `avg_latency_ms` (float ≥ 0), `p95_latency_ms` (float ≥ 0), `by_risk_level` (objeto `{low: int, medium: int, high: int}`) y `by_model_version` (objeto `{<model_version>: int, ...}`).

#### Scenario: Returns aggregates over persisted predictions
- **GIVEN** existen predicciones persistidas con varios `model_version` y `risk_level`
- **WHEN** un cliente hace `GET /metrics/summary`
- **THEN** el servicio responde `200 OK` y `total` coincide con `COUNT(*)`, `avg_latency_ms` con el promedio, `by_risk_level` cubre los 3 buckets (cero si no hay registros) y `by_model_version` enumera todas las versiones presentes

#### Scenario: Empty table returns zeros
- **GIVEN** la tabla `prediction_requests` está vacía
- **WHEN** un cliente hace `GET /metrics/summary`
- **THEN** el servicio responde `200 OK` con `total = 0`, `avg_latency_ms = 0`, `p95_latency_ms = 0`, `by_risk_level = {low: 0, medium: 0, high: 0}`, `by_model_version = {}`

### Requirement: Database connectivity at startup
The system SHALL validar la conectividad a PostgreSQL durante el `lifespan` de la aplicación, ejecutando `SELECT 1` antes de aceptar requests. Si la conexión falla, el startup MUST abortar con error explícito; NO SE PERMITE servir requests con DB caída.

#### Scenario: Missing or unreachable database aborts startup
- **WHEN** la aplicación intenta arrancar y `DATABASE_URL` apunta a un host inaccesible o credenciales inválidas
- **THEN** el startup falla propagando la excepción, y el servicio NO queda escuchando

#### Scenario: Successful connection is logged
- **WHEN** la aplicación arranca con DB accesible
- **THEN** el log incluye un mensaje confirmando la conexión y el `pool_size` configurado, antes de aceptar requests
