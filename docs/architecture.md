# Arquitectura

Documento vivo. Se actualiza al final de cada semana junto con [decisions.md](decisions.md).

---

## Vista de alto nivel (objetivo S6)

```
                       ┌────────────────────────┐
                       │       Client / curl    │
                       └───────────┬────────────┘
                                   │ HTTP
                                   ▼
                  ┌────────────────────────────────┐
                  │     FastAPI (app/main.py)      │
                  │   ── /health                   │
                  │   ── POST /risk-score          │
                  │   ── POST /batch-predictions   │
                  │   ── GET  /predictions/...     │
                  │   ── GET  /metrics             │
                  └─────┬───────────┬──────────────┘
                        │           │
            sync write  │           │ publish event
                        ▼           ▼
                ┌──────────────┐  ┌──────────────┐
                │  PostgreSQL  │  │ RabbitMQ /   │
                │              │  │   Kafka      │
                └──────────────┘  └──────┬───────┘
                        ▲                │ consume
                        │                ▼
                        │        ┌──────────────┐
                        │        │   Worker     │
                        │        │ (Celery / pika)
                        │        └──────┬───────┘
                        │               │
                        │               ▼
                        │       ┌──────────────┐
                        └──────►│  ML Model    │
                          write │  (joblib)    │
                                └──────────────┘

      Observabilidad transversal:
      FastAPI + Worker  ──►  logs estructurados (stdout)
                        ──►  /metrics (Prometheus)
                        ──►  Grafana dashboards
```

---

## Capas

| Capa              | Responsabilidad                        | Tecnología            |
| ----------------- | -------------------------------------- | --------------------- |
| **API**           | Validar input, ruteo, contrato OpenAPI | FastAPI + Pydantic    |
| **Service**       | Lógica de negocio, orquestación        | Python puro           |
| **Repository**    | Acceso a DB                            | SQLAlchemy            |
| **Model service** | Cargar modelo, predecir, versionar     | Scikit-learn + Joblib |
| **Worker**        | Procesamiento asincrónico              | Consumer de cola      |
| **Messaging**     | Eventos / desacople                    | RabbitMQ / Kafka      |
| **Persistence**   | Historial de predicciones, jobs        | PostgreSQL            |
| **Observability** | Logs, métricas, dashboards             | Prometheus + Grafana  |

---

## Contratos clave

### POST /risk-score (online)

Request:

```json
{
  "income": 1200,
  "age": 30,
  "debt": 400,
  "employment_years": 2
}
```

Response:

```json
{
  "request_id": "uuid",
  "risk_score": 0.72,
  "risk_level": "medium",
  "model_version": "v1.0.0",
  "latency_ms": 12
}
```

### POST /batch-predictions (S4+)

- Multipart con CSV.
- Devuelve `job_id` con estado inicial `PENDING`.
- Worker procesa registros y actualiza estado: `PROCESSING` → `COMPLETED` / `FAILED`.

### Evento `risk_prediction_requested` (S5+)

```json
{
  "event_id": "uuid",
  "event_type": "risk_prediction_requested",
  "payload": {
    "request_id": "uuid",
    "customer_data": { ... }
  },
  "created_at": "2026-05-20T12:34:56Z"
}
```

---

## Modelo de datos (S3+)

```sql
prediction_requests (
  id              BIGSERIAL PRIMARY KEY,
  request_id      UUID UNIQUE NOT NULL,
  input_payload   JSONB NOT NULL,
  prediction      JSONB NOT NULL,
  model_version   TEXT NOT NULL,
  latency_ms      INTEGER NOT NULL,
  source          TEXT NOT NULL,   -- 'online' | 'batch'
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

batch_jobs (
  id              BIGSERIAL PRIMARY KEY,
  job_id          UUID UNIQUE NOT NULL,
  status          TEXT NOT NULL,                  -- PENDING | PROCESSING | COMPLETED | FAILED
  total_records   INTEGER NOT NULL,
  processed       INTEGER NOT NULL DEFAULT 0,
  failed          INTEGER NOT NULL DEFAULT 0,
  started_at      TIMESTAMPTZ,
  finished_at     TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- En `prediction_requests` (S4): columnas `job_id UUID NULL` y `external_id TEXT NULL`
-- + índice único parcial `(job_id, external_id) WHERE job_id IS NOT NULL AND external_id IS NOT NULL`
-- para idempotencia por job sin afectar el path online.
```

---

## Principios

1. **Contrato primero.** El schema Pydantic manda; cambios de contrato son decisiones explícitas.
2. **Idempotencia.** `request_id` y `job_id` permiten reintentos sin duplicar efectos.
3. **Observabilidad desde el día 1.** Cada predicción se loguea con `request_id`, `model_version`, `latency_ms`.
4. **Desacoplar lo caro.** Inferencia batch va por cola, no por request HTTP largo.
5. **Versionado de modelo explícito.** El artefacto en disco lleva versión; la respuesta también.
6. **Rollback es trivial.** Cambiar `MODEL_PATH` + reiniciar = vuelta a la versión anterior.

---

## Trade-offs registrados

Ver [decisions.md](decisions.md) para el detalle de cada decisión (qué se eligió, qué se descartó, por qué).
