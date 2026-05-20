## ADDED Requirements

### Requirement: Health endpoint
The system SHALL expose `GET /health` that returns HTTP 200 with body `{"status": "ok"}` siempre que el proceso esté vivo. No depende de recursos externos.

#### Scenario: Health check responds OK
- **WHEN** un cliente hace `GET /health`
- **THEN** el servicio responde `200 OK` con `Content-Type: application/json` y body exactamente `{"status": "ok"}`

### Requirement: Risk scoring (mock)
The system SHALL exponer `POST /risk-score` que acepta un payload JSON con los campos `income` (float > 0), `age` (int, 18–100 inclusive), `debt` (float ≥ 0) y `employment_years` (int ≥ 0), y devuelve un `RiskScoreResponse` con `request_id` (UUID v4 generado en servidor), `risk_score` (float en [0, 1]), `risk_level` (uno de `"low" | "medium" | "high"`) y `model_version` (string).

El cálculo en esta versión MUST ser determinista y mockeado:
- `ratio = debt / income`
- `risk_score = clip(ratio, 0.0, 1.0)`
- `risk_level = "low"` si `risk_score < 0.33`, `"medium"` si `risk_score < 0.66`, `"high"` en caso contrario.
- `model_version = "mock-0.1"`.

#### Scenario: Happy path low risk
- **WHEN** se envía `{"income": 10000, "age": 30, "debt": 1000, "employment_years": 5}` a `POST /risk-score`
- **THEN** el servicio responde `200 OK` con `risk_score ≈ 0.1`, `risk_level == "low"`, `model_version == "mock-0.1"` y un `request_id` UUID válido

#### Scenario: Happy path high risk
- **WHEN** se envía `{"income": 1000, "age": 40, "debt": 5000, "employment_years": 2}` a `POST /risk-score`
- **THEN** el servicio responde `200 OK` con `risk_score == 1.0` y `risk_level == "high"`

#### Scenario: Invalid input is rejected
- **WHEN** se envía un payload donde `income <= 0`, `age < 18`, `age > 100`, `debt < 0` o `employment_years < 0`
- **THEN** el servicio responde `422 Unprocessable Entity` con detalle de los campos inválidos y no ejecuta el cálculo

#### Scenario: Missing field is rejected
- **WHEN** se envía un payload al que le falta cualquiera de los cuatro campos requeridos
- **THEN** el servicio responde `422 Unprocessable Entity`

### Requirement: Prediction lookup placeholder
The system SHALL exponer `GET /predictions/{id}` como placeholder de la futura capacidad de persistencia. Mientras no exista almacenamiento, MUST responder `501 Not Implemented` con un body explicativo.

#### Scenario: Lookup is not implemented
- **WHEN** un cliente hace `GET /predictions/{cualquier-id}`
- **THEN** el servicio responde `501 Not Implemented` con un body JSON que incluye un campo `detail` describiendo que la funcionalidad aún no está disponible

### Requirement: OpenAPI documentation
The system SHALL publicar la documentación OpenAPI generada por FastAPI en `/docs` (Swagger UI) y `/openapi.json`, reflejando los schemas Pydantic de request y response.

#### Scenario: Docs are reachable
- **WHEN** un cliente hace `GET /docs`
- **THEN** el servicio responde `200 OK` con HTML de Swagger UI listando los tres endpoints (`/health`, `/risk-score`, `/predictions/{id}`)
