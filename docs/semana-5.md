# Semana 5 — Mensajería + worker asincrónico

**Objetivo:** sacar el procesamiento fuera de la API y meterlo en un worker que consume una cola.

**Tag al cerrar:** `v0.5`

## Resumen del sprint

- RabbitMQ corre en Docker Compose con UI en http://localhost:15672.
- La API valida el CSV, guarda `csv_blob`, crea el job `PENDING` y publica `{job_id}` en `batch_jobs.process`.
- El worker separado (`python -m app.worker.main`) consume con ack manual, procesa desde DB, limpia `csv_blob` al finalizar y recupera jobs huerfanos al startup.
- Los tests agregan marca `worker` y cubren processor/recovery; los tests de submission ya validan enqueue en vez de procesamiento inline.

## Como testear localmente

```powershell
docker compose up -d postgres rabbitmq
alembic upgrade head
pytest -m integration
pytest -m worker
```

Stack completo:

```powershell
docker compose up -d --build
```

---

## Qué estudiar

- Patrones producer / consumer.
- Event-driven architecture.
- RabbitMQ: exchanges, queues, bindings, ack/nack.
- Alternativa: Kafka (topics, particiones, offsets).
- Dead Letter Queue (DLQ).
- At-least-once vs exactly-once delivery.
- Idempotencia en consumers.
- Diseño de eventos (event_id, event_type, payload, timestamp, version).

---

## Qué construir

### Docker Compose suma RabbitMQ

```yaml
rabbitmq:
  image: rabbitmq:3-management
  ports: ["5672:5672", "15672:15672"]   # AMQP + UI
```

UI: http://localhost:15672 (guest/guest).

### Evento

```json
{
  "event_id": "uuid",
  "event_type": "risk_prediction_requested",
  "version": "1",
  "payload": {
    "request_id": "uuid",
    "job_id": "uuid|null",
    "customer_data": { ... }
  },
  "created_at": "2026-05-20T12:34:56Z"
}
```

### Flujo

```
API  ──publish──►  exchange  ──►  queue: risk.predictions  ──consume──►  Worker
                                          │ DLX on nack/timeout
                                          ▼
                                   queue: risk.predictions.dlq
```

### Worker

`app/workers/prediction_worker.py`:

- Conecta a RabbitMQ (`pika` o `aio-pika`).
- Suscribe a `risk.predictions`.
- Por cada mensaje: deserializa → predice → guarda → ack.
- Si falla N veces: nack → DLQ.
- Loguea cada paso con `event_id`.

Corre como **proceso separado**: `python -m app.workers.prediction_worker`.

### Cambios en la API

- POST `/risk-score` puede operar en dos modos (registrar decisión):
  - **sync**: predice inline, guarda, devuelve resultado.
  - **async**: publica evento, devuelve `202 Accepted` con `request_id`.
- POST `/batch-predictions` publica un evento por fila en vez de hacer BackgroundTask.

---

## Tareas

- [ ] Agregar `pika` (o `aio-pika`) a `requirements.txt`.
- [ ] RabbitMQ en `docker-compose.yml`.
- [ ] `app/messaging/publisher.py` con `publish_event(event_type, payload)`.
- [ ] `app/workers/prediction_worker.py` consumer.
- [ ] DLQ configurada.
- [ ] Migrar batch processing a publicar eventos.
- [ ] Idempotencia en consumer (usar `event_id` para deduplicar).
- [ ] Tests del publisher (mock de canal) + tests del worker (procesar mensaje sintético).
- [ ] `docker-compose.yml` define servicio `worker` aparte de `api`.
- [ ] Documentar cómo arrancar API + worker juntos.
- [ ] Commit + tag `v0.5`.

---

## Decisiones a registrar

- ¿RabbitMQ o Kafka? Razón.
- ¿Endpoint `/risk-score` queda sync, async, o ambos?
- ¿Cómo configuro retries (max attempts, delay)?
- ¿Política de DLQ: alerta inmediata o cola para reproceso manual?

Anotar en [decisions.md](decisions.md).

---

## Criterios de cierre

- API + worker corren en contenedores separados.
- Publicar evento → worker lo procesa → predicción persistida.
- Tirar al worker, publicar mensajes → al levantar el worker, los procesa.
- Mensaje malformado → DLQ.
- Tests del publisher y del consumer pasan.

---

## Preguntas para entrevista al cerrar S5

- ¿Cuándo usar cola y cuándo no?
- ¿Diferencia entre RabbitMQ y Kafka? ¿Cuándo cada uno?
- ¿Cómo garantizás procesamiento idempotente?
- ¿Qué pasa si el worker se cae a mitad de un mensaje?
- ¿Qué es una DLQ y cuándo la usás?
- ¿Cómo escalarías el worker horizontalmente?
