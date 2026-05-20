## 1. Project scaffolding

- [x] 1.1 Crear `requirements.txt` con `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `pytest`, `httpx`, `anyio` (rangos `>=X,<Y`)
- [x] 1.2 Crear `.gitignore` extra para `.venv/`, `__pycache__/`, `.pytest_cache/`, `*.egg-info/` (si no están ya)
- [x] 1.3 Crear árbol `app/__init__.py`, `app/main.py`, `app/config.py`, `app/api/__init__.py`, `app/api/routes/__init__.py`, `app/schemas/__init__.py`, `app/services/__init__.py`
- [x] 1.4 Crear árbol `tests/__init__.py`, `tests/conftest.py`

## 2. Configuración

- [x] 2.1 Implementar `app/config.py` con `Settings(BaseSettings)` (al menos `app_name`, `model_version="mock-0.1"`), carga desde `.env`
- [x] 2.2 Actualizar `.env.example` con las variables expuestas por `Settings`

## 3. Schemas Pydantic

- [x] 3.1 `app/schemas/prediction.py`: `RiskScoreRequest` con `income: float = Field(gt=0)`, `age: int = Field(ge=18, le=100)`, `debt: float = Field(ge=0)`, `employment_years: int = Field(ge=0)`
- [x] 3.2 Mismo archivo: `RiskScoreResponse` con `request_id: UUID`, `risk_score: float`, `risk_level: Literal["low","medium","high"]`, `model_version: str`

## 4. Servicio de scoring (mock)

- [x] 4.1 `app/services/prediction_service.py`: función pura `score(request: RiskScoreRequest) -> RiskScoreResponse` que aplica `clip(debt/income, 0, 1)`, bucketiza en low/medium/high, genera `request_id = uuid4()` y setea `model_version` desde `Settings`
- [x] 4.2 Exponer un `get_prediction_service()` (dependency) para poder inyectarlo en los routers

## 5. Routers FastAPI

- [x] 5.1 `app/api/routes/health.py`: `GET /health` → `{"status": "ok"}`
- [x] 5.2 `app/api/routes/predictions.py`: `POST /risk-score` que delega en el servicio vía `Depends`
- [x] 5.3 Mismo archivo: `GET /predictions/{prediction_id}` que devuelve `HTTPException(status_code=501, detail="Prediction lookup not implemented yet")`

## 6. App bootstrap

- [x] 6.1 `app/main.py`: crear `FastAPI(title=..., version="0.1.0")`, montar routers de health y predictions, exponer `/docs` (default)
- [x] 6.2 Verificar manualmente `uvicorn app.main:app --reload` levanta sin warnings y `/docs` lista los tres endpoints

## 7. Tests

- [x] 7.1 `tests/conftest.py`: fixture `client` con `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`; configurar `anyio_backend = "asyncio"` (o `pytest.ini`)
- [x] 7.2 `tests/test_health.py`: test `/health` → 200 + body `{"status":"ok"}`
- [x] 7.3 `tests/test_predictions.py`: happy path low risk (income=10000, debt=1000) → 200, `risk_level=="low"`, `model_version=="mock-0.1"`, `request_id` parsea como UUID
- [x] 7.4 Mismo archivo: happy path high risk (debt > income) → `risk_score == 1.0`, `risk_level=="high"`
- [x] 7.5 Mismo archivo: 422 cuando `income <= 0` y cuando falta un campo
- [x] 7.6 Mismo archivo: `GET /predictions/abc` → 501 con `detail` describiendo not implemented
- [x] 7.7 Verificar `pytest` pasa con ≥5 tests en verde

## 8. Docker + DX

- [x] 8.1 `Dockerfile` base `python:3.11-slim`: copiar `requirements.txt`, `pip install --no-cache-dir`, copiar `app/`, `CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]`, `EXPOSE 8000`
- [x] 8.2 Verificar `docker build -t risk-api .` termina OK
- [ ] 8.3 (Opcional) Probar `docker run -p 8000:8000 risk-api` y `curl localhost:8000/health`

## 9. Documentación

- [x] 9.1 Actualizar `README.md` con: setup (venv + `pip install -r requirements.txt`), run (`uvicorn ...`), test (`pytest`), docker (`build`/`run`), y nota grande de que el scoring es **mock**
- [x] 9.2 Mencionar que `/predictions/{id}` aún responde 501

## 10. Cierre

- [ ] 10.1 Commit: `feat(api): scaffold FastAPI service with mock risk scoring`
- [ ] 10.2 Tag `v0.1`
- [ ] 10.3 Marcar tareas del roadmap (`docs/semana-1.md`) y dejar listo para archivar este change con `/opsx:archive`
