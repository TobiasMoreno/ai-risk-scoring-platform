## Why

El contrato HTTP de `/risk-score` está estable desde S1, pero el cálculo es un mock (`clip(debt/income, 0, 1)`). Para que el servicio empiece a parecerse a producción y se ejerciten ciclos reales de entrenamiento + serialización + carga, S2 sustituye el mock por un modelo Scikit-learn entrenado y servido vía `joblib`. Sin este paso, el resto del roadmap (persistencia, batch, observabilidad) opera sobre un score sin valor predictivo.

## What Changes

- Añadir script `app/models/train_model.py`: genera dataset sintético (features `income`, `age`, `debt`, `employment_years`; target `risk` binario derivado de reglas + ruido), hace `train_test_split`, entrena `LogisticRegression`, imprime métricas (accuracy/precision/recall/F1/confusion matrix) y persiste con `joblib.dump` en `app/models/risk_model.joblib`.
- Añadir `app/services/model_service.py` con `ModelService` que: carga el `.joblib` desde disco, expone `predict(request) -> RiskScoreResponse`, loguea `model_version` y `latency_ms`.
- Cargar el modelo **una vez al startup** vía `lifespan` de FastAPI (no por request). Si el archivo no existe o está corrupto, el servicio MUST fallar al arrancar con un error claro.
- Reemplazar `PredictionService` (mock) en `POST /risk-score` por `ModelService`. `prediction_service.py` se elimina.
- **BREAKING semántico** (no de shape): `model_version` cambia de `"mock-0.1"` a `"v0.2.0"` (configurable vía `Settings.model_version` / `MODEL_VERSION` en `.env`). El shape de `RiskScoreResponse` se conserva.
- Tests: mockean `ModelService` (no entrenan en cada corrida). Verifican `risk_score ∈ [0,1]`, `model_version` presente y configurable, `risk_level` consistente con el score. Test específico para el fallo de startup cuando falta el modelo.
- Dependencias nuevas: `scikit-learn`, `joblib`, `numpy` (pandas opcional, sólo si se usa para el dataset).
- Documentación: README documenta `python -m app.models.train_model` como paso previo a `uvicorn`. `docs/decisions.md` registra: LogReg vs RandomForest, sintético vs público, thresholds de bucketing, política ante "modelo no cargado".

## Capabilities

### New Capabilities
<!-- Ninguna nueva en S2. -->

### Modified Capabilities
- `risk-scoring-api`: el requirement "Risk scoring (mock)" pasa a ser **"Risk scoring (ML model)"** — el algoritmo es un `LogisticRegression` cargado al startup; `model_version` deja de estar hardcodeado a `"mock-0.1"`. Se añade un requirement nuevo de **startup health**: el servicio MUST fallar al arrancar si el modelo no puede cargarse.

## Impact

- **Código nuevo**: `app/models/train_model.py`, `app/services/model_service.py`, `app/models/risk_model.joblib` (artifact binario versionado o gitignored — ver design).
- **Código modificado**: `app/api/routes/predictions.py` (usa `ModelService`), `app/main.py` (lifespan que carga el modelo), `app/config.py` (`model_path`, `model_version` configurables), `app/schemas/prediction.py` (sin cambios en shape).
- **Código eliminado**: `app/services/prediction_service.py` (queda obsoleto).
- **Dependencias**: `scikit-learn>=1.4,<2.0`, `joblib>=1.3,<2.0`, `numpy>=1.26,<3.0`.
- **Imagen Docker**: crece (scikit-learn pesa). Se reusa base `python:3.11-slim`; sin necesidad de multi-stage todavía.
- **Tests**: existentes para `risk-score` se ajustan (ya no validan `model_version == "mock-0.1"`); usan un `ModelService` mock vía dependency override.
- **Tag al cerrar**: `v0.2`.
