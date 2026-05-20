# AI Risk Scoring Platform

Backend platform que expone un modelo simple de **risk scoring** en condiciones tipo producción: API de inferencia online, procesamiento batch, persistencia, cola + worker asincrónico y observabilidad.

> Proyecto principal de la [ruta de estudio de 6 semanas](docs/ruta-estudio.md) para migrar de Backend tradicional → **Backend Engineer en AI/ML Platform**.

---

## Estado actual

Semana en curso: **S1 — Fundamentos + FastAPI** (ver [docs/semana-1.md](docs/semana-1.md)).

| Semana | Tema                                  | Tag    | Estado    |
| ------ | ------------------------------------- | ------ | --------- |
| S1     | FastAPI + endpoints mock              | `v0.1` | en curso  |
| S2     | Modelo Scikit-learn + inferencia real | `v0.2` | pendiente |
| S3     | PostgreSQL + historial                | `v0.3` | pendiente |
| S4     | Jobs batch + CSV                      | `v0.4` | pendiente |
| S5     | Cola + worker asincrónico             | `v0.5` | pendiente |
| S6     | Observabilidad + portfolio            | `v1.0` | pendiente |

---

## Cómo empezar

1. Leer [docs/setup.md](docs/setup.md) — instalación de Python, Docker, Poetry/uv en Windows.
2. Leer [docs/semana-1.md](docs/semana-1.md) — qué construir esta semana y cómo.
3. Levantar el proyecto:

```powershell
# entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# dependencias (cuando exista pyproject.toml / requirements.txt)
pip install -r requirements.txt

# correr la API
uvicorn app.main:app --reload
```

API local: http://localhost:8000 — docs en http://localhost:8000/docs

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
