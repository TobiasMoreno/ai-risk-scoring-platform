## MODIFIED Requirements

### Requirement: Risk scoring (ML model)
The system SHALL exponer `POST /risk-score` que acepta un payload JSON con los campos `income` (float > 0), `age` (int, 18–100 inclusive), `debt` (float ≥ 0) y `employment_years` (int ≥ 0), y devuelve un `RiskScoreResponse` con `request_id` (UUID v4 generado en servidor), `risk_score` (float en [0, 1]), `risk_level` (uno de `"low" | "medium" | "high"`) y `model_version` (string).

El cálculo MUST provenir de un modelo Scikit-learn (pipeline `StandardScaler → LogisticRegression`) entrenado offline y persistido como `app/models/risk_model.joblib`:
- `risk_score = model.predict_proba(features)[:, 1]` (probabilidad de la clase positiva = "alto riesgo"), clipado a [0, 1].
- `risk_level = "low"` si `risk_score < 0.33`, `"medium"` si `risk_score < 0.66`, `"high"` en caso contrario.
- `model_version` MUST leerse de `Settings.model_version` (configurable vía `MODEL_VERSION` en `.env`). Default: `"v0.2.0"`.

El modelo MUST cargarse **una sola vez al startup** del proceso (vía `lifespan` de FastAPI) y reusarse entre requests; no SE PERMITE cargar el modelo por request.

#### Scenario: Happy path returns a probability-based score
- **WHEN** se envía un payload válido a `POST /risk-score`
- **THEN** el servicio responde `200 OK` con `risk_score` en `[0, 1]`, `risk_level` consistente con los umbrales 0.33 / 0.66, `model_version` igual al valor configurado en `Settings` y un `request_id` UUID válido

#### Scenario: model_version reflects configuration
- **WHEN** `MODEL_VERSION=v0.2.1` está seteado al arrancar el proceso
- **THEN** toda respuesta de `POST /risk-score` MUST incluir `model_version == "v0.2.1"`

#### Scenario: Invalid input is rejected
- **WHEN** se envía un payload donde `income <= 0`, `age < 18`, `age > 100`, `debt < 0` o `employment_years < 0`
- **THEN** el servicio responde `422 Unprocessable Entity` con detalle de los campos inválidos y no invoca el modelo

#### Scenario: Missing field is rejected
- **WHEN** se envía un payload al que le falta cualquiera de los cuatro campos requeridos
- **THEN** el servicio responde `422 Unprocessable Entity`

## ADDED Requirements

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
