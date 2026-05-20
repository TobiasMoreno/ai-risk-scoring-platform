## 1. Dependencias y settings

- [x] 1.1 Añadir a `requirements.txt`: `scikit-learn>=1.4,<2.0`, `joblib>=1.3,<2.0`, `numpy>=1.26,<3.0`
- [x] 1.2 Actualizar `app/config.py`: añadir `model_path: str = "app/models/risk_model.joblib"` y cambiar `model_version` default a `"v0.2.0"`
- [x] 1.3 Actualizar `.env.example`: `MODEL_VERSION=v0.2.0` (con comentario explicando que el binario se genera con `train_model.py`)
- [x] 1.4 Crear `app/models/__init__.py` vacío

## 2. Script de entrenamiento

- [x] 2.1 `app/models/train_model.py`: función `make_dataset(n=5000, seed=42)` que genera DataFrame/array con features sintéticas (`income`, `age`, `debt`, `employment_years`) y target `risk` binario derivado de reglas + 10% de ruido
- [x] 2.2 Mismo archivo: función `train()` que hace `train_test_split` (test_size=0.2, stratify=y), construye `Pipeline([StandardScaler(), LogisticRegression()])`, entrena, evalúa en test imprimiendo accuracy, precision, recall, F1 y confusion matrix
- [x] 2.3 Mismo archivo: persistir con `joblib.dump(pipeline, Settings.model_path)` y `if __name__ == "__main__": train()`
- [x] 2.4 Ejecutar `python -m app.models.train_model` y verificar que se crea `app/models/risk_model.joblib` y se imprimen métricas

## 3. ModelService

- [x] 3.1 Crear `app/services/model_service.py` con clase `ModelService` que recibe `model_path` y `model_version` en `__init__`
- [x] 3.2 Método `load()` que hace `joblib.load(model_path)` y guarda el pipeline en `self._pipeline`. Logea `model_version` y `model_path` cuando carga OK
- [x] 3.3 Método `predict(request: RiskScoreRequest) -> RiskScoreResponse`: construye vector de features en el orden esperado por el pipeline, llama `predict_proba`, toma columna de clase positiva, clipa a [0,1], bucketiza con los thresholds 0.33/0.66, devuelve `RiskScoreResponse` con `request_id=uuid4()` y `model_version=self._model_version`. Loguea `latency_ms`
- [x] 3.4 Eliminar `app/services/prediction_service.py`

## 4. Bootstrap con lifespan

- [x] 4.1 Reescribir `app/main.py`: usar `contextlib.asynccontextmanager` para definir `lifespan(app)` que crea `ModelService(...)`, llama `load()`, lo guarda en `app.state.model_service`. Si la carga falla, propagar la excepción
- [x] 4.2 Definir dependency `get_model_service(request: Request) -> ModelService` que devuelve `request.app.state.model_service`
- [x] 4.3 Pasar `lifespan=lifespan` al constructor de `FastAPI(...)`

## 5. Routers

- [x] 5.1 `app/api/routes/predictions.py`: reemplazar `Depends(get_prediction_service)` por `Depends(get_model_service)` y llamar `service.predict(payload)`
- [x] 5.2 Verificar que `GET /predictions/{id}` sigue devolviendo 501 (sin cambios)

## 6. Tests

- [x] 6.1 Actualizar `tests/conftest.py`: añadir fixture que inyecta un `FakeModelService` vía `app.dependency_overrides[get_model_service]`, para que los tests no carguen `joblib`
- [x] 6.2 `FakeModelService.predict(...)` devuelve `RiskScoreResponse` determinista (por ejemplo: `risk_score = min(request.debt / max(request.income, 1), 1.0)`, `model_version = "test-1.0"`)
- [x] 6.3 Actualizar `tests/test_predictions.py`: ya no asertar `model_version == "mock-0.1"`; asertar que es `"test-1.0"` con el fake. Mantener happy path low/high, 422 paramétrico, missing field, 501 lookup
- [x] 6.4 Añadir test que verifica que el cliente recibe `risk_score ∈ [0, 1]` y `risk_level` consistente con los umbrales
- [x] 6.5 Añadir test de startup failure: en un test aislado, configurar `Settings.model_path` a un path inexistente y verificar que instanciar el `lifespan` propaga la excepción (probar `ModelService.load()` directamente alcanza; no es necesario levantar la app completa)
- [x] 6.6 Correr `pytest` y verificar verde (≥10 tests)

## 7. Documentación

- [x] 7.1 `README.md`: añadir sección **"Entrenar el modelo"** con `python -m app.models.train_model` como paso previo a `uvicorn`. Quitar/ajustar el banner de "scoring mock" — ahora el scoring es real pero sigue siendo un modelo de juguete sobre datos sintéticos
- [x] 7.2 `docs/decisions.md`: registrar (a) LogReg vs RandomForest (b) dataset sintético vs público (c) thresholds 0.33/0.66 (d) política "modelo no cargado = startup falla" (e) binario gitignored
- [x] 7.3 `docs/semana-2.md`: marcar las tareas del roadmap

## 8. Docker

- [x] 8.1 Actualizar `Dockerfile`: copiar `app/models/risk_model.joblib` también (si existe localmente). Documentar en README que el binario debe entrenarse antes de `docker build`
- [x] 8.2 Verificar `docker build -t risk-api .` termina OK
- [x] 8.3 (Opcional) `docker run -p 8000:8000 risk-api` y `curl POST /risk-score`

## 9. Cierre

- [x] 9.1 Commit: `feat(api): replace mock scoring with scikit-learn LogisticRegression model`
- [ ] 9.2 Tag `v0.2` (lo hace el usuario manualmente)
- [x] 9.3 Archivar este change con `/opsx:archive`
