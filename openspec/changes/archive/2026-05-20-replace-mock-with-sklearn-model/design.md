## Context

S1 dejó el contrato HTTP estable (`/risk-score` con `RiskScoreRequest` / `RiskScoreResponse`) y un `PredictionService` mock detrás de un `Depends(...)`. El punto de extensión ya existe; S2 sólo cambia la implementación que está detrás de la dependency y agrega el ciclo de vida del modelo (entrenamiento + serialización + carga). Persistencia, drift detection, y A/B testing entran en semanas posteriores — esta iteración no debe atarse a esas decisiones.

## Goals / Non-Goals

**Goals:**
- Predicciones que dependen de features reales (no de la ratio `debt/income` directa).
- Modelo cargado **una sola vez** al startup, no por request (`p99` < ~5ms para un LR pequeño).
- Re-entrenamiento reproducible vía un único comando: `python -m app.models.train_model`.
- `model_version` configurable desde `.env` — la versión del binario y la versión reportada en la response viven en `Settings`.
- Tests rápidos: no entrenan; usan dependency override de FastAPI para inyectar un `ModelService` falso.

**Non-Goals:**
- Modelo bueno: el objetivo es la mecánica, no el AUC. Dataset sintético basta.
- Feature engineering serio (scaling, encoding, interaccions). Sólo lo mínimo (StandardScaler dentro del pipeline).
- MLflow / experiment tracking / model registry. Disco local + `model_version` en `.env`.
- A/B testing, canary, shadow mode.
- Persistir el resultado en DB — eso es S3.
- Detección de drift / monitoring de calidad.

## Decisions

### 1. Algoritmo: `LogisticRegression` (no Random Forest)
- LogReg es el "hola mundo" de clasificación; explica fácil en entrevista (coeficientes, sigmoide, regularización).
- Genera probabilidades calibradas vía `predict_proba` sin trucos. RF requiere calibración para que `predict_proba` sea "honesto".
- Dataset sintético es lineal-friendly; RF no aporta sobre estos features.
- Decisión registrada en `docs/decisions.md`.

**Alternativa descartada:** RandomForestClassifier — mejor para no-linealidad pero overkill aquí.

### 2. Dataset: sintético
- 5–10k filas generadas en `train_model.py` con reglas simples + ruido gaussiano: `risk = 1` si `(debt/income > 0.5) XOR (employment_years < 2)` con ~10% de flip aleatorio.
- Seed fija (`numpy.random.seed(42)`) → reproducible.

**Alternativa descartada:** German Credit / public dataset — añade descarga, licencias, encoding categórico. No vale el costo en S2.

### 3. Pipeline: `StandardScaler → LogisticRegression`
- `sklearn.pipeline.Pipeline` para que `predict()` reciba features crudas y el scaler viva dentro del joblib. Esto evita el bug clásico de "entrené con scaling, sirvo sin scaling".
- Una sola llamada a `joblib.dump(pipeline, ...)`.

### 4. Carga al startup vía `lifespan`
- FastAPI deprecó `on_event("startup")`. Uso `contextlib.asynccontextmanager` + `lifespan=...`.
- El `ModelService` se construye con `(model_path, model_version)` desde `Settings`, llama a `load()` y se guarda en `app.state.model_service`.
- Dependency `get_model_service(request: Request)` devuelve `request.app.state.model_service` → reemplazable en tests con `app.dependency_overrides`.

**Alternativa descartada:** carga perezosa (en el primer request). Primer request sufre latencia; además enmascara modelos rotos hasta que llega tráfico.

### 5. Política ante "modelo no cargado"
- Si `joblib.load()` falla (archivo ausente, corrupto, versión incompatible de sklearn), `lifespan` re-raisea → uvicorn no termina de levantar. Mejor failure rápido que servir 500s.
- `train_model.py` SE EJECUTA OFFLINE; el contenedor de la API NO debe entrenar al arrancar. README lo deja explícito.

### 6. Bucketing de `risk_level`
- Mantengo los mismos umbrales que S1: `<0.33` → low, `<0.66` → medium, resto → high. Permite comparar distribuciones mock vs real en `docs/decisions.md`.
- El bucketing vive en `ModelService.predict()` (no en el modelo) — el modelo devuelve probabilidad, el servicio la traduce.

### 7. `model_version` configurable
- `Settings.model_version` lee `MODEL_VERSION` desde `.env`. Default en código: `"v0.2.0"`.
- El binario `.joblib` no contiene la versión; vivir con la convención "el que arrancó la app dice qué versión es" es suficiente hasta que haya registry. Riesgo: mismatch entre binario y string. Mitigación: `train_model.py` puede aceptar `--version` y escribir un `version.txt` junto al `.joblib` (futuro, no S2).

### 8. Versionado del binario en repo
- Decisión: **gitignorear** `app/models/*.joblib` (ya está en `.gitignore`).
- Quien ejecute la app la primera vez corre `python -m app.models.train_model`. Trade-off: el repo no carga un binario; el README hace el contrato explícito.
- Alternativa (rechazada para v0.2): commitear el binario para "clone + uvicorn" funcione sin paso intermedio. Acumular binarios en git es feo a largo plazo.

### 9. Eliminación de `prediction_service.py`
- Borrar antes que dejar como "wrapper deprecated" — el servicio mock no tiene utilidad futura y sólo confunde. El test que mockeaba scoring se reescribe contra `ModelService`.

### 10. Logging
- `ModelService.predict()` loguea `model_version` y `latency_ms` con `logging.getLogger(__name__).info(...)`. Sin structured logging todavía — S6 entra observabilidad.

## Risks / Trade-offs

- **Modelo sintético no es predictivo en producción**: aceptado; señalizado por `model_version="v0.2.0"` y un disclaimer en README. Riesgo de confusión externa → mitigación: README dice "modelo de juguete".
- **Versión de sklearn al cargar ≠ versión al entrenar**: `joblib` puede romper o emitir warning. Mitigación: pinear `scikit-learn>=1.4,<2.0` en requirements y dejar a futuro mover a hash-pinning + Dockerfile que entrena en build.
- **Binario no en repo**: clone fresco requiere `train_model.py` antes de `uvicorn`. Mitigación: README + log claro si falta el archivo.
- **Carga al startup bloquea el arranque** si el modelo es grande → no aplica con LogReg (KBs), pero se vuelve relevante en S2+ si se sube a RF/gradient boosting grande. Aceptable por ahora.
- **Threshold global** (`0.33`, `0.66`) puede ser sub-óptimo según métrica de negocio (precisión vs recall). Decisión consciente: thresholds fijos hasta S6.

## Migration Plan

- Cliente HTTP **no** ve cambios de shape. Sólo cambia el valor literal de `model_version` y la distribución de `risk_score`.
- Quien hace `git pull` y tenía la app corriendo con el mock:
  1. `pip install -r requirements.txt` (nuevas deps).
  2. `python -m app.models.train_model` (genera el `.joblib`).
  3. `uvicorn app.main:app --reload`.
- Rollback: `git revert` del commit de S2 + `git checkout v0.1`.

## Open Questions

- ¿Acepto `--version` en `train_model.py` para escribir el string en `Settings` automáticamente? — posponer; sobre-ingeniería para v0.2.
- ¿Vale la pena un `Makefile` / script PowerShell `train.ps1` para encapsular el comando? — posponer hasta que haya más de un paso.
