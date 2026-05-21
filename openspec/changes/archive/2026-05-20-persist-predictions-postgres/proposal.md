## Why

Hasta S2, cada predicción se calcula y se devuelve sin dejar rastro. Es imposible auditar qué se sirvió, comparar versiones de modelo, ni alimentar dashboards. S3 introduce persistencia transaccional en PostgreSQL: cada `POST /risk-score` se guarda atómicamente y se expone vía endpoints de consulta y agregación. Además habilita el camino para S4 (batch) y S5 (cola) — sin tabla, no hay historial al cual escribir.

## What Changes

- **Infra local**: añadir `docker-compose.yml` con `postgres:16`, volumen `pgdata`, vars desde `.env`.
- **Conexión**: `app/db/database.py` con engine SQLAlchemy 2.x **sync** y `SessionLocal` factory. `DATABASE_URL` desde `Settings`.
- **Modelo**: `app/db/models.py` con `PredictionRequest` (`id BIGSERIAL PK`, `request_id UUID UNIQUE`, `input_payload JSONB`, `prediction JSONB`, `model_version TEXT`, `latency_ms INTEGER`, `source TEXT` default `'online'`, `created_at TIMESTAMPTZ` default `now()`). Índice en `created_at DESC` y en `model_version`.
- **Migraciones**: `alembic init` + primera revisión que crea `prediction_requests`. `alembic.ini` lee `sqlalchemy.url` de la env. README documenta `alembic upgrade head`.
- **Repository**: `app/repositories/prediction_repository.py` con `save / get_by_id / list_recent(limit, offset) / summary()`. La capa de servicio nunca toca `Session` directo.
- **Service**: `ModelService.predict()` ya loguea `latency_ms`; ahora lo devuelve también. `app/services/prediction_service.py` (NUEVO, distinto al mock de S1) orquesta `model.predict()` + `repo.save()` en una sola transacción.
- **Endpoints**:
  - `POST /risk-score` ahora persiste antes de responder (sin cambiar el shape de la response — `latency_ms` no se expone en el contrato HTTP todavía).
  - `GET /predictions/{request_id}` deja de ser 501; devuelve el registro o 404.
  - **NUEVO** `GET /predictions?limit=N&offset=M` lista las últimas predicciones, default `limit=50`, `limit ≤ 200`.
  - **NUEVO** `GET /metrics/summary` devuelve `{ total, avg_latency_ms, p95_latency_ms, by_risk_level: {low, medium, high}, by_model_version: {...} }`.
- **Tests**: integration tests contra Postgres real levantado por `docker compose up -d postgres`. Fixture `db_session` con `BEGIN` + `ROLLBACK` por test para aislamiento (no `create_all` por test). Si la DB no está disponible, los tests de integración se **skipean** (no fallan) — los tests unitarios (S1/S2) siguen verdes sin DB.
- **Dependencias**: `sqlalchemy>=2.0,<3.0`, `psycopg[binary]>=3.1,<4.0`, `alembic>=1.13,<2.0`.
- **Docs**: README documenta `docker compose up -d postgres` + `alembic upgrade head` + `uvicorn`. `decisions.md` registra ADR-06 a ADR-09 (sync vs async, JSONB vs columnas, repository, PK strategy).

## Capabilities

### New Capabilities
<!-- Ninguna nueva en S3. -->

### Modified Capabilities
- `risk-scoring-api`:
  - **REMOVED** "Prediction lookup placeholder" (el 501 desaparece).
  - **MODIFIED** "Risk scoring (ML model)" — ahora persiste el resultado en DB antes de responder.
  - **ADDED** "Prediction lookup by request_id" — `GET /predictions/{request_id}` devuelve 200 con el registro o 404.
  - **ADDED** "Recent predictions listing" — `GET /predictions` paginado.
  - **ADDED** "Predictions summary metrics" — `GET /metrics/summary`.
  - **ADDED** "Database connectivity at startup" — la app valida `DATABASE_URL` y aborta si no puede conectarse.

## Impact

- **Código nuevo**: `app/db/{__init__.py, database.py, models.py}`, `app/repositories/{__init__.py, prediction_repository.py}`, `app/services/prediction_service.py` (orquestación), `alembic/`, `docker-compose.yml`.
- **Código modificado**: `app/config.py` (DATABASE_URL, db_pool_size), `app/main.py` (lifespan crea engine y verifica `SELECT 1`), `app/api/routes/predictions.py` (rutas nuevas + ya no 501), `app/services/model_service.py` (devolver `latency_ms`).
- **Dependencias**: +`sqlalchemy`, +`psycopg[binary]`, +`alembic`.
- **Docker image**: crece marginalmente (psycopg trae libpq).
- **Tests**: el suite existente sigue corriendo sin DB; tests nuevos requieren DB local. CI futuro deberá levantar postgres en service container.
- **Operativo**: clone fresco ahora requiere `docker compose up -d postgres && alembic upgrade head` antes de `uvicorn`.
- **Tag al cerrar**: `v0.3`.
