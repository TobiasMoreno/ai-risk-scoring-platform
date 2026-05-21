# AI Risk Scoring Platform

Backend platform que expone un modelo simple de **risk scoring** en condiciones tipo producción: API de inferencia online, procesamiento batch, persistencia, cola + worker asincrónico y observabilidad.

> Proyecto principal de la [ruta de estudio de 6 semanas](docs/ruta-estudio.md) para migrar de Backend tradicional → **Backend Engineer en AI/ML Platform**.

---

## Estado actual

Semana en curso: **S6 — Observabilidad + portfolio** (ver [docs/semana-6.md](docs/semana-6.md)).

| Semana | Tema                                  | Tag    | Estado    |
| ------ | ------------------------------------- | ------ | --------- |
| S1     | FastAPI + endpoints mock              | `v0.1` | hecho     |
| S2     | Modelo Scikit-learn + inferencia real | `v0.2` | hecho     |
| S3     | PostgreSQL + historial                | `v0.3` | hecho     |
| S4     | Jobs batch + CSV                      | `v0.4` | hecho     |
| S5     | Cola + worker asincrónico             | `v0.5` | hecho     |
| S6     | Observabilidad + portfolio            | `v1.0` | en curso  |

---

> ⚠️ **Modelo de juguete.** El scoring usa un `LogisticRegression` (Scikit-learn) entrenado sobre un **dataset sintético**. No es predictivo en producción; el objetivo es ejercitar el ciclo entrenamiento → serialización → carga. `model_version` viene de `.env` (`MODEL_VERSION=v0.2.0` por default).

## Cómo empezar

1. Leer [docs/setup.md](docs/setup.md) — instalación de Python, Docker, Poetry/uv en Windows.
2. Leer [docs/semana-1.md](docs/semana-1.md) — qué construir esta semana y cómo.
3. Levantar el proyecto:

```powershell
# entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# dependencias
pip install -r requirements.txt

# levantar PostgreSQL + RabbitMQ local
docker compose up -d postgres rabbitmq

# aplicar migraciones
alembic upgrade head

# entrenar el modelo (necesario antes de arrancar)
python -m app.models.train_model

# correr la API (terminal 1)
uvicorn app.main:app --reload

# correr el worker batch (terminal 2)
python -m app.worker.main
```

API local: http://localhost:8000 — docs en http://localhost:8000/docs

### Re-entrenar el modelo

El binario `app/models/risk_model.joblib` está **gitignored**: cada clone fresco debe ejecutarlo una vez antes del primer `uvicorn`.

```powershell
python -m app.models.train_model
```

Imprime métricas (accuracy / precision / recall / F1 / confusion matrix) sobre el split de test y guarda el pipeline `StandardScaler → LogisticRegression`. Si el archivo no existe al arrancar, la API **falla al startup** con `FileNotFoundError` — comportamiento intencional.

### Base de datos

PostgreSQL corre en Docker (`docker-compose.yml`). El puerto mapeado es **55432** para no chocar con instalaciones nativas en 5432/5433.

```powershell
# solo infra (modo dev: la API corre con uvicorn en el host)
docker compose up -d postgres rabbitmq

# stack completo (Postgres + RabbitMQ + API + worker, API en :8000, migra automáticamente)
docker compose up -d --build

# parar (mantiene datos)
docker compose stop

# tirar todo (incluye volumen pgdata)
docker compose down -v
```

El servicio `api` aplica `alembic upgrade head` al arrancar y luego levanta `uvicorn`. RabbitMQ expone AMQP en `:5672` y la UI de management en http://localhost:15672 (`guest`/`guest` por default).

### Migraciones (Alembic)

Cada cambio de modelo en `app/db/models.py` requiere una nueva revisión:

```powershell
# crear una nueva revisión autogenerada (revisar siempre el SQL resultante)
alembic revision --autogenerate -m "<descripción>"

# aplicar
alembic upgrade head

# rollback de la última
alembic downgrade -1
```

`DATABASE_URL` se lee desde `.env` (ver `alembic/env.py`).

### Tests

```powershell
# todos (requiere Postgres up + alembic upgrade head; usar --basetemp si Windows bloquea Temp)
pytest --basetemp .pytest_tmp

# solo unit (sin DB)
pytest -m "not integration"

# solo integration
pytest -m integration

# tests del worker (requieren RabbitMQ corriendo)
pytest -m worker
```

### Predicciones batch (CSV)

`POST /batch-predictions` acepta un CSV con headers `income,age,debt,employment_years,external_id` (los primeros 4 obligatorios; `external_id` opcional, da idempotencia por job). El servidor responde `202` con `job_id`, publica el job en RabbitMQ y el worker lo procesa mientras el cliente consulta estado por polling.

```powershell
# 1) Subir el CSV (devuelve job_id y 'Location' header)
curl -F file=@samples/sample_batch.csv http://localhost:8000/batch-predictions

# 2) Poll del estado
curl http://localhost:8000/batch-predictions/<job_id>

# 3) Descargar resultados (paginado)
curl "http://localhost:8000/batch-predictions/<job_id>/results?limit=50&offset=0"
```

State machine: `PENDING → PROCESSING → (COMPLETED | FAILED)`. `FAILED` sólo si ninguna fila se persistió. Filas inválidas incrementan `failed` pero no abortan el job. Repetir el mismo `external_id` dentro de un job se descarta (UNIQUE parcial en DB). Default 10 MB por upload, 1000 filas por chunk — configurable vía `BATCH_MAX_UPLOAD_BYTES` y `BATCH_CHUNK_SIZE`.

### Docker

```powershell
# recomendado: stack completo con DB, RabbitMQ, API y worker
docker compose up -d --build

# ver logs de API y worker
docker compose logs -f api worker
```

---

## Arquitectura objetivo (al final de S6)

```
Client
  │
  ▼
FastAPI ── PostgreSQL
  │
  ▼
Queue (RabbitMQ/Kafka) ──► Worker ──► ML Model ──► PostgreSQL
                                          │
                                          ▼
                                  Logs + Metrics
                                          │
                                          ▼
                                Prometheus / Grafana
```

Detalle en [docs/architecture.md](docs/architecture.md).

---

## Stack

- **Lenguaje**: Python 3.11+
- **API**: FastAPI + Pydantic
- **ML**: Scikit-learn + Joblib
- **DB**: PostgreSQL
- **Cola**: RabbitMQ (o Kafka)
- **Observabilidad**: Prometheus + Grafana + logs estructurados
- **Infra local**: Docker Compose
- **Tests**: Pytest

---

## Índice de documentación

| Doc                                                                         | Para qué sirve                                       |
| --------------------------------------------------------------------------- | ---------------------------------------------------- |
| [docs/ruta-estudio.md](docs/ruta-estudio.md)                                | Ruta completa de 6 semanas (objetivo, brecha, stack) |
| [docs/setup.md](docs/setup.md)                                              | Cómo dejar el entorno local listo en Windows         |
| [docs/architecture.md](docs/architecture.md)                                | Arquitectura, capas y trade-offs                     |
| [docs/semana-1.md](docs/semana-1.md) → [docs/semana-6.md](docs/semana-6.md) | Playbook semana por semana                           |
| [docs/glosario.md](docs/glosario.md)                                        | Glosario AI/ML (training, inference, drift, etc.)    |
| [docs/decisions.md](docs/decisions.md)                                      | Bitácora de decisiones técnicas (ADR-lite)           |
| [docs/entrevista.md](docs/entrevista.md)                                    | Preguntas + respuestas base para entrevista          |
| [docs/roadmap.md](docs/roadmap.md)                                          | Roadmap consolidado + checklist de progreso          |
| [docs/contribuir.md](docs/contribuir.md)                                    | Convenciones de Git, ciclo semanal, definition of done |

---

## Workflow recomendado

- Una rama por semana: `semana-1`, `semana-2`, ...
- Cierre de semana = merge a `main` + tag (`v0.1`, `v0.2`, ...).
- Actualizar [docs/decisions.md](docs/decisions.md) cada vez que se elige A en lugar de B.
- Cada semana suma código _y_ docs. Si no está documentado, no está hecho.
