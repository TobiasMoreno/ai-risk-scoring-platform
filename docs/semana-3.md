# Semana 3 — PostgreSQL + historial

**Objetivo:** persistir cada predicción, exponer historial, entender la diferencia OLTP vs OLAP (BigQuery conceptual).

**Tag al cerrar:** `v0.3`

---

## Qué estudiar

- PostgreSQL básico: tipos, índices, JSONB, UUID.
- SQLAlchemy 2.x (sync o async — elegir y registrar).
- Alembic para migraciones.
- Diferencia OLTP (transaccional) vs OLAP (analítico).
- BigQuery conceptual: por qué columnar, particionado, clustering. Sin tocarlo realmente.
- Queries agregadas: `GROUP BY`, `COUNT`, `AVG`, `PERCENTILE_CONT`.

---

## Qué construir

### Docker Compose con PostgreSQL

`docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: risk_scoring
      POSTGRES_USER: risk
      POSTGRES_PASSWORD: changeme
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]

volumes:
  pgdata:
```

### Esquema

```sql
prediction_requests (
  id, request_id, input_payload, prediction,
  model_version, latency_ms, source, created_at
)
```

Ver [architecture.md](architecture.md#modelo-de-datos-s3) para el SQL completo.

### Migraciones con Alembic

- `alembic init alembic`
- Configurar `sqlalchemy.url` desde `DATABASE_URL`.
- Primera migración: crear `prediction_requests`.

### Repository pattern

`app/repositories/prediction_repository.py`:

```python
class PredictionRepository:
    def save(self, request_id, input, prediction, model_version, latency_ms, source) -> None
    def get_by_id(self, request_id: UUID) -> PredictionRecord | None
    def list_recent(self, limit: int = 50) -> list[PredictionRecord]
    def summary(self) -> SummaryStats
```

### Endpoints nuevos

```
GET /predictions             → últimas N predicciones (paginado)
GET /predictions/{id}        → por request_id
GET /metrics/summary         → total, latencia promedio, distribución de risk levels
```

---

## Tareas

- [ ] Agregar `sqlalchemy`, `psycopg[binary]`, `alembic` a `requirements.txt`.
- [ ] `docker-compose.yml` con PostgreSQL.
- [ ] `app/db/database.py` con engine + session factory.
- [ ] Modelos SQLAlchemy.
- [ ] Alembic init + primera migración.
- [ ] `PredictionRepository` con tests (usando DB de test o `pytest-postgresql`).
- [ ] `prediction_service` guarda después de predecir.
- [ ] Endpoints de consulta.
- [ ] Tests de integración (al menos con SQLite in-memory si la DB real complica).
- [ ] Documentar cómo levantar la DB y aplicar migraciones.
- [ ] Commit + tag `v0.3`.

---

## Decisiones a registrar

- ¿SQLAlchemy sync o async?
- ¿`JSONB` para `input_payload` o columnas tipadas?
- ¿Repository pattern o uso directo de Session?
- ¿UUID como PK o `id` autoincremental + `request_id` UNIQUE?

Anotar en [decisions.md](decisions.md).

---

## Criterios de cierre

- `docker compose up -d postgres` levanta DB.
- `alembic upgrade head` aplica migración.
- POST `/risk-score` guarda en DB.
- GET `/predictions/{id}` devuelve lo guardado.
- GET `/metrics/summary` devuelve agregados reales.
- Tests de integración pasan.

---

## Preguntas para entrevista al cerrar S3

- ¿Diferencia entre OLTP y OLAP?
- ¿Para qué usarías BigQuery?
- ¿Cómo indexarías una tabla de predicciones para queries por `created_at` y `model_version`?
- ¿Cómo procesarías un CSV con millones de registros sin tirar la DB?
- ¿Por qué JSONB y no columnas tipadas? ¿Cuándo conviene cada una?
