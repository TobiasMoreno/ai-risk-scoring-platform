## 1. Infra local

- [x] 1.1 Crear `docker-compose.yml` con servicio `postgres:16`, env desde `.env` (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`), volumen `pgdata`, `ports: ["5432:5432"]`, `healthcheck` con `pg_isready`
- [x] 1.2 Verificar `docker compose up -d postgres` levanta y `docker compose ps` muestra healthy
- [x] 1.3 Confirmar que `.env.example` tiene `DATABASE_URL=postgresql+psycopg://risk:changeme@localhost:5432/risk_scoring` (ajustar driver a psycopg v3)

## 2. Dependencias y settings

- [x] 2.1 Añadir a `requirements.txt`: `sqlalchemy>=2.0,<3.0`, `psycopg[binary]>=3.1,<4.0`, `alembic>=1.13,<2.0`
- [x] 2.2 Actualizar `app/config.py`: añadir `database_url: str` (lee `DATABASE_URL`), `db_pool_size: int = 5`, `db_max_overflow: int = 5`

## 3. Capa de DB

- [x] 3.1 Crear `app/db/__init__.py` vacío
- [x] 3.2 `app/db/database.py`: función `create_engine_from_settings(settings) -> Engine` con `pool_pre_ping=True`; `SessionLocal = sessionmaker(bind=..., autoflush=False, expire_on_commit=False)`
- [x] 3.3 `app/db/models.py`: `Base = declarative_base()` y modelo `PredictionRequest` (tabla `prediction_requests`): `id BIGSERIAL PK`, `request_id UUID UNIQUE NOT NULL`, `input_payload JSONB NOT NULL`, `prediction JSONB NOT NULL`, `model_version Text NOT NULL`, `latency_ms Integer NOT NULL`, `source Text NOT NULL DEFAULT 'online'`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Índices: `(created_at DESC)`, `(model_version)`
- [x] 3.4 Dependency `get_db()` en `app/db/database.py`: cede una `Session`, hace `commit/rollback/close` en el `finally`

## 4. Alembic

- [x] 4.1 `alembic init alembic` (template sync)
- [x] 4.2 Editar `alembic/env.py` para que `target_metadata = Base.metadata` y `sqlalchemy.url` venga de `os.environ["DATABASE_URL"]`
- [x] 4.3 Generar revisión inicial: `alembic revision --autogenerate -m "create prediction_requests"`
- [x] 4.4 Revisar el SQL generado a mano (índices, `JSONB`, `now()`)
- [x] 4.5 Aplicar: `alembic upgrade head` contra la DB local; verificar tabla creada con `\d prediction_requests`

## 5. Repository

- [x] 5.1 `app/repositories/__init__.py` vacío
- [x] 5.2 `app/repositories/prediction_repository.py`: clase `PredictionRepository(session: Session)` con métodos `save(...) -> PredictionRequest`, `get_by_request_id(uuid) -> PredictionRequest | None`, `list_recent(limit: int, offset: int) -> list[PredictionRequest]`, `summary() -> SummaryStats`
- [x] 5.3 Definir `SummaryStats` (pydantic o dataclass) con `total`, `avg_latency_ms`, `p95_latency_ms`, `by_risk_level: dict[str,int]`, `by_model_version: dict[str,int]`
- [x] 5.4 `summary()` usa una sola query con CTE: `COUNT`, `AVG(latency_ms)`, `PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms)`, `prediction->>'risk_level'`, `model_version`

## 6. Service + ModelService

- [x] 6.1 `app/services/model_service.py`: que `predict()` devuelva también `latency_ms` (sin cambiar el `RiskScoreResponse` HTTP — devolver un objeto interno o tupla)
- [x] 6.2 Crear `app/services/prediction_service.py` (distinto del mock viejo) con `PredictionService(model: ModelService, repo: PredictionRepository)` y método `score_and_persist(payload) -> RiskScoreResponse` que orquesta predict + save en una transacción
- [x] 6.3 Dependency `get_prediction_service(db = Depends(get_db), model = Depends(get_model_service))` arma el servicio por request

## 7. Routers

- [x] 7.1 `app/api/routes/predictions.py`: `POST /risk-score` usa `Depends(get_prediction_service)` y llama `service.score_and_persist(payload)`
- [x] 7.2 `GET /predictions/{request_id}` (path param `UUID`): consulta repo, devuelve `PredictionRecord` o `404`
- [x] 7.3 `GET /predictions?limit=50&offset=0`: query params validados (`limit: int = Query(50, ge=1, le=200)`, `offset: int = Query(0, ge=0)`), devuelve lista
- [x] 7.4 Crear `app/api/routes/metrics.py`: `GET /metrics/summary` que llama `repo.summary()` y devuelve `SummaryStats`
- [x] 7.5 Registrar el router de metrics en `app/main.py`
- [x] 7.6 Schemas de response: definir `PredictionRecordResponse` (con `created_at` ISO 8601, `input_payload`, `prediction` como dicts) y `SummaryResponse`

## 8. App bootstrap

- [x] 8.1 `app/main.py` lifespan: además de cargar el modelo, crear engine con `create_engine_from_settings(...)`, hacer `engine.connect().execute(text("SELECT 1"))`, guardar en `app.state.db_engine` y `app.state.SessionLocal`. Loguear `pool_size` y URL censurada
- [x] 8.2 `get_db()` toma `SessionLocal` desde `app.state` (no global)
- [x] 8.3 Si la conectividad falla, propagar excepción → uvicorn no arranca

## 9. Tests

- [x] 9.1 Marcar tests existentes que mockean DB con `@pytest.mark.unit` (default si no se marca). Configurar `pytest.ini` con `markers = unit, integration` y opción `--no-integration` opcional
- [x] 9.2 `tests/conftest.py`: añadir fixture `db_engine` (scope session) que intenta conectar a la DB de test; si falla, `pytest.skip("DB not available")` para los tests marcados `integration`
- [x] 9.3 Aplicar Alembic en setup: `command.upgrade(alembic_cfg, "head")` programático en el fixture `db_engine`
- [x] 9.4 Fixture `db_session` (scope function): conecta, `BEGIN`, bindea Session, al final `ROLLBACK` + `close`
- [x] 9.5 Fixture `client_with_db`: builds una FastAPI app con `dependency_overrides[get_db] = lambda: db_session` y `dependency_overrides[get_model_service] = FakeModelService(...)`. Usa `ASGITransport`
- [x] 9.6 `tests/test_predictions_persistence.py` (integration): `POST /risk-score` crea fila en DB; `GET /predictions/{id}` devuelve 200; `GET /predictions/{id-no-existe}` devuelve 404; `GET /predictions/no-uuid` 422
- [x] 9.7 Mismo archivo: `GET /predictions?limit=2` devuelve sólo 2 ordenados DESC; `limit=500` → 422
- [x] 9.8 `tests/test_metrics.py` (integration): inserta filas con varios `risk_level` y `model_version`, llama `GET /metrics/summary`, verifica `total`, `by_risk_level`, `by_model_version`. Tabla vacía → zeros
- [x] 9.9 `tests/test_repository.py` (integration): tests directos del repo (`save`, `get_by_request_id`, `list_recent`, `summary`)
- [x] 9.10 Verificar que los tests unitarios (S1/S2) siguen verdes sin DB (`pytest -m unit` o sin marker)
- [x] 9.11 Correr suite completo con DB up: `pytest -q` (≥20 tests verdes)

## 10. Documentación

- [x] 10.1 README: sección **"Base de datos"** con `docker compose up -d postgres`, `alembic upgrade head` y nueva orden de comandos al arrancar (db → migración → train_model → uvicorn)
- [x] 10.2 README: sección **"Migraciones"** con `alembic revision --autogenerate -m "..."` + workflow
- [x] 10.3 `docs/decisions.md`: ADR-06 (SQLAlchemy sync), ADR-07 (JSONB), ADR-08 (Repository), ADR-09 (BIGSERIAL + UUID UNIQUE). Renumerar comentarios "próximas" del template
- [x] 10.4 `docs/semana-3.md`: marcar tareas del roadmap
- [x] 10.5 `docs/architecture.md`: ajustar el SQL del modelo de datos si la migración real difiere (campos `NOT NULL`, índices)

## 11. Docker

- [x] 11.1 Actualizar `Dockerfile` si hace falta `libpq` (psycopg[binary] trae todo; verificar build)
- [x] 11.2 Verificar `docker build -t risk-api .` termina OK
- [x] 11.3 (Opcional) Probar `docker compose up` con `postgres` + `api` (añadir servicio `api` al compose, depende del healthcheck de postgres). Si se complica, dejar para S5
- [x] 11.4 Smoke test end-to-end: con compose arriba, `curl POST /risk-score`, `curl GET /predictions/{id}`, `curl GET /metrics/summary` (verificado en proceso vía ASGITransport con DB real)

## 12. Cierre

- [ ] 12.1 Commit: `feat(api): persist predictions in postgres and add lookup/listing/metrics endpoints`
- [ ] 12.2 Tag `v0.3` (el usuario lo hace manual)
- [ ] 12.3 Archivar este change con `/opsx:archive`
