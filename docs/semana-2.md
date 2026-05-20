# Semana 2 — Modelo simple + inferencia real

**Objetivo:** reemplazar el mock por un modelo de Scikit-learn entrenado y servirlo desde la API.

**Tag al cerrar:** `v0.2`

---

## Qué estudiar

- Scikit-learn: `LogisticRegression`, `RandomForestClassifier`, `train_test_split`.
- Métricas: accuracy, precision, recall, F1, confusion matrix.
- Overfitting vs underfitting (intuitivo).
- Serialización: `joblib.dump` / `joblib.load`.
- Carga lazy del modelo en FastAPI (al startup, no por request).
- Versionado de modelo en disco + en response.

---

## Qué construir

### Script de entrenamiento

`app/models/train_model.py`:

1. Genera dataset sintético (o usa uno público chico: German Credit, etc.).
2. Features: `income`, `age`, `debt`, `employment_years`.
3. Target: `risk` binario (0 = low, 1 = high) — derivable de reglas + ruido.
4. Train/test split.
5. Entrena `LogisticRegression`.
6. Imprime métricas.
7. Guarda con `joblib.dump(model, "app/models/risk_model.joblib")`.

### Model service

`app/services/model_service.py`:

```python
class ModelService:
    def __init__(self, path: str, version: str): ...
    def load(self) -> None: ...
    def predict(self, features: dict) -> RiskPrediction: ...
```

- Carga al `startup` de FastAPI.
- Expone `predict()` que toma el payload validado y devuelve score + level.
- Loguea `model_version`, `latency_ms`.

### Endpoint actualizado

`POST /risk-score` ahora usa `ModelService.predict()`. La respuesta incluye `model_version` real (leído de `.env`/config).

---

## Tareas

- [x] Agregar `scikit-learn`, `joblib`, `numpy`, `pandas` a `requirements.txt`.
- [x] Script `train_model.py` que genera, entrena, evalúa y guarda.
- [x] `ModelService` con load + predict.
- [x] Cargar modelo en `app.main` con `@app.on_event("startup")` o `lifespan`.
- [x] Endpoint `POST /risk-score` consume el modelo real.
- [x] Test que mockea `ModelService` (no entrena en cada test).
- [x] Test que valida que la respuesta tiene `model_version` y `risk_score` en [0,1].
- [x] Documentar en README cómo re-entrenar el modelo.
- [x] Commit + tag `v0.2`.

---

## Decisiones a registrar

- ¿Logistic vs Random Forest? Razón.
- ¿Dataset sintético vs público? Razón.
- ¿Threshold para low/medium/high? (ej: <0.33, <0.66, resto).
- ¿Cómo manejo el caso "modelo no cargado" al arrancar?

Anotar en [decisions.md](decisions.md).

---

## Criterios de cierre

- `python app/models/train_model.py` produce `risk_model.joblib` + imprime métricas.
- API responde con predicciones reales (no constantes).
- `model_version` en la response coincide con `.env`.
- Tests pasan sin necesidad de entrenar (mock del service).
- README documenta el flujo de entrenamiento.

---

## Preguntas para entrevista al cerrar S2

- ¿Por qué cargo el modelo al startup y no por request?
- ¿Cómo versionarías el modelo en producción?
- ¿Cómo manejarías un rollback?
- ¿Qué pasa si el modelo serializado está corrupto?
- ¿Cuál es la diferencia entre `joblib` y `pickle`?
