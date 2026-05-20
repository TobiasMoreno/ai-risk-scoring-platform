# Ruta de estudio — Backend → AI/ML Platform

Resumen operativo de la ruta de 6 semanas. El documento extenso original vive fuera del repo (`ruta-backend-ai-ml-platform.md`); acá queda la versión accionable.

---

## Objetivo

Migrar desde Backend tradicional hacia **Backend Software Engineer en AI/ML Platform**: APIs, pipelines, jobs, mensajería, model serving y observabilidad.

> NO apunta a Data Scientist, ML Researcher ni ML Engineer puro.

Roles target:

- Backend Software Engineer - AI/ML Platform
- Backend Engineer, GenAI
- AI Platform Engineer / ML Platform Engineer

---

## Posicionamiento

> Backend Developer con experiencia en sistemas productivos, APIs, integraciones y observabilidad, enfocado en plataformas AI/ML: data pipelines, model serving, procesamiento asincrónico y monitoreo de modelos en producción.

---

## Brecha técnica

### Ya tengo base sólida

Backend, APIs REST, microservicios, integraciones, observabilidad, AWS, sistemas productivos, procesos asincrónicos.

### A reforzar

Python, FastAPI, BigQuery, pipelines de datos, jobs batch, colas (Kafka/RabbitMQ/SQS), ML básico, model serving, MLOps básico, observabilidad aplicada a modelos.

---

## Stack

| Capa           | Tecnología                                                |
| -------------- | --------------------------------------------------------- |
| Lenguaje       | Python 3.11+ (sumando a Java/Spring)                      |
| API            | FastAPI + Pydantic + OpenAPI                              |
| ML             | Scikit-learn + Joblib                                     |
| Datos          | PostgreSQL + SQL + BigQuery (conceptual)                  |
| Procesamiento  | Jobs batch, cron, Celery/RQ                               |
| Mensajería     | RabbitMQ / Kafka / AWS SQS                                |
| Observabilidad | Prometheus + Grafana + OpenTelemetry + logs estructurados |
| Infra          | Docker + Docker Compose                                   |
| Tests          | Pytest                                                    |

---

## Las 6 semanas

| Semana | Foco                                         | Doc                        |
| ------ | -------------------------------------------- | -------------------------- |
| S1     | Fundamentos + FastAPI + endpoints mock       | [semana-1.md](semana-1.md) |
| S2     | Modelo Scikit-learn + inferencia real        | [semana-2.md](semana-2.md) |
| S3     | PostgreSQL + historial + BigQuery conceptual | [semana-3.md](semana-3.md) |
| S4     | Jobs batch + CSV                             | [semana-4.md](semana-4.md) |
| S5     | Mensajería + worker asincrónico              | [semana-5.md](semana-5.md) |
| S6     | Observabilidad + portfolio                   | [semana-6.md](semana-6.md) |

---

## Criterio de éxito

Listo para aplicar cuando pueda:

- [ ] Explicar qué hace un Backend Engineer en AI/ML Platform.
- [ ] Construir una API que sirva un modelo.
- [ ] Procesar predicciones batch.
- [ ] Usar una cola con worker.
- [ ] Guardar historial y resultados.
- [ ] Medir latencia, errores y volumen.
- [ ] Documentar arquitectura y trade-offs.
- [ ] Defender el proyecto en entrevista.

Checklist completa en [roadmap.md](roadmap.md).
