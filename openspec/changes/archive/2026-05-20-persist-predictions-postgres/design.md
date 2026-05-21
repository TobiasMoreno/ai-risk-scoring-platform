## Context

S1 dejó la API; S2 puso un modelo real detrás. Ambas iteraciones son stateless. S3 introduce el primer recurso stateful (PostgreSQL) y, con él, decisiones que van a marcar la base para batch (S4), workers (S5) y métricas (S6). El objetivo es elegir defaults razonables sin sobre-ingeniería: una tabla, un repo, una conexión sync, migraciones versionadas. Nada de event sourcing, multi-tenant, soft-deletes, ni outbox todavía.

## Goals / Non-Goals

**Goals:**
- Cada `POST /risk-score` deja un registro persistente con todos los datos para auditarlo y reproducirlo.
- Endpoints `GET /predictions/{id}`, `GET /predictions?limit=`, `GET /metrics/summary` listos para alimentar un dashboard simple.
- Capa de DB aislada detrás de un repository; los servicios y routers no ven `Session`.
- Migraciones versionadas con Alembic — el schema vive en código, no en SQL ad-hoc.
- Tests de integración corren contra Postgres real, no contra SQLite; los unitarios existentes no necesitan DB.

**Non-Goals:**
- Async / `asyncpg` — sync es suficiente para los QPS de este proyecto y simplifica todo (sesiones, tests, transacciones).
- ORM avanzado (joins, relationships, lazy loading) — la tabla está aislada.
- Soft deletes, auditoría temporal, particionado por fecha — entran si/cuando duela.
- Cachear consultas (`GET /metrics/summary`) — la query es barata; si pesa, S6 ataca con materialized views o Prometheus.
- Multi-tenant / multi-DB / read replicas.
- Outbox pattern para eventos — entra en S5 cuando exista cola.

## Decisions

### 1. SQLAlchemy 2.x **sync**
- `asyncpg` exige que TODO el stack sea async (engine, session, repo, service, routers). Es más código y más cuidado en tests.
- A 10–100 RPS contra una DB local en el mismo host, sync no es bottleneck.
- FastAPI corre rutas sync en threadpool — perfectamente válido.
- Si en S5/S6 medimos contention y duele, se migra; el repository pattern aísla el cambio.

**Alternativa descartada:** async SQLAlchemy + `asyncpg`.

### 2. `psycopg` v3 (no v2, no `psycopg2`)
- v3 es la rama mantenida; v2 está en modo soporte.
- `psycopg[binary]` evita compilar C extensions en Windows.

### 3. `JSONB` para `input_payload` y `prediction`
- El shape de input/response es estable (4 features fijos, 4 campos en response) → columnas tipadas serían factibles.
- Pero el modelo va a evolucionar (S4 batch puede traer features extra; S5 puede traer metadata). JSONB absorbe sin migración.
- Las queries actuales no filtran por contenido del payload — sólo por `request_id`, `created_at`, `model_version`, `risk_level` (este último vive en `prediction`). Si en algún momento se filtra por `risk_level`, se agrega un índice GIN o una columna calculada — barato.

**Alternativa descartada:** columnas tipadas (`income REAL`, `risk_score REAL`, etc.). Demasiada cirugía por cada cambio de schema.

### 4. PK: `BIGSERIAL id` + `UUID request_id UNIQUE`
- `BIGSERIAL` ordena naturalmente por inserción, ocupa 8 bytes, es ideal para keysets/paginado.
- `request_id UUID` es el identificador externo (lo ve el cliente, vive en logs, sirve para correlación).
- Lo mejor de ambos: índice clusterizado barato en `id`, lookup por `request_id` igualmente rápido vía UNIQUE.

**Alternativa descartada:** `UUID` como PK. Más bytes, peor localidad, más fragmentación de páginas. UUID v7 lo mitigaría pero psycopg/SQLAlchemy aún no lo emiten cómodo.

### 5. Repository pattern (no Session directo en servicios)
- Repo expone métodos de dominio (`save_prediction`, `get_by_request_id`, `list_recent`, `summary`); no expone `Session`.
- El servicio (`PredictionService`) recibe `repo` por DI y delega.
- Beneficio: tests del servicio mockean el repo trivialmente; tests del repo van contra DB real.
- Costo: una capa más. Aceptado — el alternativo "Session everywhere" se vuelve doloroso en cuanto crece el equipo o la cantidad de queries.

### 6. Transacciones
- Una transacción por request HTTP, manejada por un dependency `get_db()` que abre `SessionLocal()` y hace `commit` / `rollback` / `close` en el `finally`.
- `PredictionService.score_and_persist(payload)` ejecuta `model.predict()` (puro, no toca DB) + `repo.save(...)` dentro de la misma sesión. Si `save` falla, la sesión hace rollback y la API devuelve 500. **No** se devuelve la predicción si no se persistió — la durabilidad es parte del contrato.

### 7. Alembic
- `alembic init alembic` con template async no, sync sí.
- `alembic.ini` lee `sqlalchemy.url` de env via `env.py` (`os.environ["DATABASE_URL"]`).
- Migración inicial autogenerada y luego revisada a mano (la autogen no detecta índices personalizados correctamente todas las veces).
- README explícito: cada cambio de modelo → revisión nueva, nunca editar revisiones aplicadas.

### 8. Pool de conexiones
- `pool_size=5, max_overflow=5, pool_pre_ping=True` para tolerar conexiones cerradas por idle timeout de Postgres.
- `Settings.db_pool_size` configurable.

### 9. Lifecycle: lifespan crea engine y prueba conectividad
- En `lifespan(app)`: crear engine, hacer `engine.connect().execute(text("SELECT 1"))`, guardar en `app.state.db_engine`.
- Si falla → propaga, uvicorn no arranca. Misma política que el modelo.
- `get_db()` toma el engine desde `app.state` para no instanciar uno nuevo por request.

### 10. Tests de integración
- Fixture `db_engine` (scope session): conecta a la DB local; si no responde, **skip** todos los tests marcados `@pytest.mark.integration`.
- Fixture `db_session` (scope function): abre conexión, `BEGIN`, da una `Session` ligada a esa conexión, al final `ROLLBACK` y `close`. Aislamiento perfecto, sin recrear schema por test.
- El schema lo aplica una vez `alembic upgrade head` en `conftest.py` (idempotente) o asumimos que el dev ya lo corrió. Decisión: aplicar Alembic programáticamente al setup de la sesión → cero pasos manuales para el dev.

**Alternativa descartada:** SQLite in-memory. Diverge en JSONB, `now()`, percentiles, índices. Cualquier divergencia se paga en producción.

### 11. Endpoints de listing / summary
- `GET /predictions?limit=50&offset=0` — paginado simple por `offset/limit`. Sirve hasta volúmenes medianos; cuando duela, keyset pagination con `created_at < ?`.
- `GET /metrics/summary` — agregados sobre los últimos N (configurable, default todos): `COUNT`, `AVG(latency_ms)`, `PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms)`, distribución por `risk_level` extrayendo `prediction->>'risk_level'`, distribución por `model_version`. Una sola query con CTE.

### 12. Validación de inputs en endpoints nuevos
- `limit ≤ 200` (evita scan completo accidental).
- `offset ≥ 0`.
- `request_id` en path es `UUID` (Pydantic valida).

### 13. `latency_ms` no en response HTTP
- `architecture.md` muestra un response con `latency_ms`, pero el spec sellado en S1/S2 NO lo incluye y los consumidores se acostumbraron a su shape. Mantener compatibilidad: `latency_ms` se persiste, no se expone en la response. Si se quiere exponer, va con un header (`X-Latency-Ms`) en una iteración posterior.

## Risks / Trade-offs

- **Sync bloquea threads del pool**: cierto, pero el threadpool de FastAPI/Starlette está dimensionado para esto. Si vemos contention en S5+, migración a async + asyncpg está localizada en `database.py` + `repository.py`.
- **JSONB sin índices**: queries que filtren por `prediction->>'risk_level'` van a fullscan. Aceptable mientras la tabla sea chica; agregar `CREATE INDEX ... USING GIN (prediction)` o columna calculada cuando el dashboard lo necesite.
- **Migraciones Alembic en autogenerate** pueden detectar mal índices con condiciones / expresiones; revisión manual cada vez.
- **Persistencia obligatoria** en `/risk-score`: si la DB cae, devolvemos 500 — la API deja de servir aunque el modelo esté OK. Trade-off consciente: prefiero perder requests que servir respuestas no auditables. Mitigación futura: outbox + cola.
- **No autenticación, no rate limiting** — sigue postergado.
- **Datos PII**: `input_payload` guarda `income`, `age`, `debt`, `employment_years` literales. En producción real habría que hashear o encriptar. Para v0.3 (juguete con dataset sintético), aceptable.

## Migration Plan

- Clone fresco:
  1. `cp .env.example .env`
  2. `docker compose up -d postgres`
  3. `pip install -r requirements.txt`
  4. `alembic upgrade head`
  5. `python -m app.models.train_model`
  6. `uvicorn app.main:app --reload`
- Rollback de S3: `alembic downgrade base` deja la DB vacía. `git revert` + reinstall + retag.

## Open Questions

- ¿`source` debería ser un `Enum` PostgreSQL en lugar de `TEXT`? Decisión: TEXT por ahora; Enum cuesta migraciones cada vez que entra un valor nuevo.
- ¿Vale la pena `Index(model_version)` desde el día uno? Probable que sí; lo dejamos en la primera migración para no requerir una segunda al primer dashboard que filtre.
- ¿`/metrics/summary` debería aceptar `since=<timestamp>`? Posponer; primer dashboard saca todo.
