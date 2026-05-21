## Context

El flujo batch actual (`v0.4`) corre dentro del proceso de la API: `POST /batch-predictions` valida el CSV, crea la fila en `batch_jobs` con `status=PENDING` y dispara `BackgroundTasks` con el procesamiento (chunks de 1000 filas, persistencia por chunk, transición de estado). Esto funciona para un solo proceso pero tiene tres problemas conocidos:

1. **Sin durabilidad ante restarts**: si el contenedor de la API se reinicia mid-job, `batch_jobs` queda en `PROCESSING` sin nadie que lo retome. Hoy no hay recovery.
2. **Acoplamiento de recursos**: una carga batch grande consume memoria y CPU del proceso que también sirve `/risk-score`, generando contención de latencia online.
3. **No escala horizontalmente**: agregar réplicas de la API multiplica también el procesamiento si el LB enruta el `POST`, y no permite escalar workers independientemente.

S5 de la ruta de estudio especifica explícitamente "cola + worker asincrónico" como pieza de plataforma ML. RabbitMQ es la opción pedida en `README.md` ("RabbitMQ o Kafka") y la más idiomática para este patrón work-queue.

El stack ya tiene `docker-compose.yml`, healthchecks, migraciones Alembic vía servicio `api`, y tests integration marcados (`pytest -m integration`).

## Goals / Non-Goals

**Goals:**
- Desacoplar `POST /batch-predictions` del procesamiento: el handler HTTP solo encola.
- Worker independiente, escalable (más réplicas = más throughput), con acks manuales y mensajes durables.
- Recuperación automática de jobs huérfanos al startup del worker.
- Mantener el contrato HTTP público de los endpoints batch **idéntico** (cliente externo no nota la diferencia salvo en el delay `PENDING → PROCESSING`).
- Tests de integración reales contra RabbitMQ del compose.

**Non-Goals:**
- Migrar el path online (`POST /risk-score`) a la cola.
- Reintentos automáticos con backoff exponencial sofisticado (basta con requeue básico en este sprint).
- Dead-letter queue (mencionado en risks, queda para S6 si emerge la necesidad).
- Métricas Prometheus de la cola (eso es S6).
- Multi-tenancy o priorización de jobs.
- Sharding del worker por modelo o tipo de payload.

## Decisions

### Decision 1: Broker = RabbitMQ (no Kafka, no Redis)

**Elegido**: RabbitMQ 3.13 (imagen `rabbitmq:3.13-management-alpine`, plugin management activo para UI en `:15672`).

**Por qué**:
- Patrón work-queue clásico: una cola, N consumers, ack manual = exactamente lo que necesitamos.
- Más liviano operacionalmente que Kafka (no requiere Zookeeper/KRaft, tooling más simple).
- RabbitMQ está mencionado por nombre en `README.md`; Kafka entraría en un proyecto separado.
- Redis Streams es viable pero menos idiomático para work-queue con acks; mantiene complejidad si después agregamos pub/sub.

**Alternativas consideradas**:
- *Kafka*: overkill para 1 cola con throughput modesto; ordering por partición no aporta acá.
- *Celery + Redis*: agrega abstracción innecesaria (Celery worker model); preferimos aprender el protocolo AMQP directo, que es el objetivo de S5.
- *Postgres SKIP LOCKED como cola*: técnicamente posible y sin nueva infra, pero no enseña lo que la ruta de estudio pide.

### Decision 2: Cliente AMQP = `aio-pika` (no `pika` síncrono)

**Elegido**: `aio-pika` para el publisher dentro de FastAPI **y** para el consumer del worker.

**Por qué**:
- FastAPI ya es asíncrono; usar `pika` síncrono obliga a `run_in_threadpool` solo para publicar. `aio-pika` se integra natural.
- Misma librería en API y worker = una sola API mental, menos código de glue.
- Reconexión automática y manejo de channels más limpio en `aio-pika`.

**Alternativas**: `pika` (síncrono, más simple pero peor fit), `kombu` (parte de Celery, demasiado abstracto).

### Decision 3: Una sola cola durable `batch_jobs.process`

- Mensaje = `{"job_id": "<uuid>"}` serializado JSON. NADA más. Toda la info adicional (CSV path, contadores) se lee de Postgres por `job_id`.
- Cola declarada como `durable=True`, mensajes publicados con `delivery_mode=2` (persistent).
- Sin exchange custom: publish al exchange default con routing_key = nombre de cola.
- `prefetch_count` configurable (default 1) para evitar que un worker reserve N mensajes y muera con todos en vuelo.

**Por qué un solo mensaje delgado**: el CSV ya está embebido en el primer commit del job (en filesystem temporal del contenedor API). Si el worker corre en otro contenedor sin acceso a ese FS, esto NO funciona — **decisión clave** abajo.

### Decision 4: CSV persistido en DB, no en filesystem

El handler HTTP actual recibe el upload y procesa el CSV en memoria. Como API y worker corren en contenedores distintos sin volumen compartido, debemos **persistir el contenido del CSV** para que el worker lo pueda leer por `job_id`.

**Elegido**: agregar columna `csv_blob BYTEA` (o `TEXT` si UTF-8 garantizado — preferimos `BYTEA` para no asumir encoding) a `batch_jobs`. La API guarda el archivo crudo al crear el job; el worker lo lee, procesa, y al transicionar a `COMPLETED/FAILED` el blob se **borra** (`UPDATE batch_jobs SET csv_blob = NULL`).

**Trade-off**: `BYTEA` ocupa espacio. Default 10 MB por upload → tolerable. Limpiar al terminar el job acota el crecimiento.

**Alternativa rechazada**: volumen Docker compartido. Funciona en compose pero rompe en producción real (containers en hosts distintos). Persistir en DB es portable.

**Alternativa futura**: object storage (S3/MinIO). Out of scope para S5; queda como upgrade natural.

### Decision 5: Recovery de jobs huérfanos al startup del worker

Al arrancar, el worker ejecuta una query:

```sql
SELECT job_id FROM batch_jobs
WHERE status = 'PROCESSING'
  AND started_at < NOW() - INTERVAL '<BATCH_ORPHAN_THRESHOLD_SECONDS> seconds';
```

Por cada `job_id` resultado, **republica** un mensaje en la cola. La idempotencia preexistente por `external_id` (UNIQUE parcial en `prediction_requests`) garantiza que reprocesar no duplica filas. Filas sin `external_id` SÍ se duplicarían — documentado como limitación conocida (mismo trade-off que el spec actual de batch).

**Threshold por qué 600s default**: cubre el caso "worker tarda 5 min en un chunk grande" sin gatillar falso recovery. Configurable vía env.

**Alternativa rechazada**: heartbeat por job (UPDATE `last_heartbeat_at` cada N segundos). Más correcto pero más complejo; el threshold simple alcanza para este sprint.

### Decision 6: Tests con RabbitMQ real, no fake

Nueva marca `pytest -m worker` que requiere `docker compose up rabbitmq` antes. Misma filosofía que ya tenemos para Postgres en integration tests.

**Por qué no fake**: el comportamiento que queremos validar (durabilidad, ack/nack, requeue) es exactamente el del broker real. Un fake en memoria nos daría falsa seguridad.

**Costo**: CI necesita levantar también `rabbitmq` además de `postgres` para correr la suite completa. Aceptable.

### Decision 7: Worker = mismo image que API, comando distinto

`Dockerfile` no cambia. En `docker-compose.yml`:

```yaml
worker:
  build: .
  command: python -m app.worker.main
  depends_on: [postgres, rabbitmq]
  environment: <misma config que api>
```

**Por qué**: misma codebase, mismas deps; no justifica una segunda imagen. Si más adelante el worker necesita libs distintas (p.ej. GPU), se splittea.

## Risks / Trade-offs

- **[CSV en DB infla `batch_jobs`]** → Mitigación: borrar `csv_blob` al transicionar a estado final. Documentar que `batch_jobs` no es archive permanente del CSV.
- **[Worker crashea entre `prediction_requests` insert y ack del mensaje]** → Mitigación: ack manual DESPUÉS de actualizar `batch_jobs.status`. Si crashea antes, mensaje requeue, recovery procesa idempotente por `external_id`. Filas sin `external_id` pueden duplicarse en este caso — documentado.
- **[Mensaje envenenado: CSV malformado que rompe siempre el worker]** → Mitigación inicial: `requeue=False` en `nack` cuando el error es de validación/parsing (descarta el mensaje, marca el job `FAILED`). En errores transitorios (DB caída) `requeue=True`. Sin DLQ por ahora.
- **[Worker no escala = backlog crece]** → Mitigación: la cola se ve en RabbitMQ UI (`:15672`). Escalado horizontal = más réplicas del servicio `worker` en compose.
- **[Tests más lentos por dependencia de RabbitMQ]** → Mitigación: marca `worker` separada; el dev puede correr `pytest -m "not worker and not integration"` para feedback rápido en unit.
- **[Recovery sweep republica mensajes en bucle si el worker sigue crasheando]** → Mitigación: el sweep solo corre al startup, no en loop. Si un worker crashea repetidamente con el mismo job, será visible en logs y UI; se interviene manualmente.

## Migration Plan

1. **Schema**: nueva migración Alembic agrega `csv_blob BYTEA NULL` a `batch_jobs`. Backfill = no aplica (los jobs viejos ya están en estado final).
2. **Deploy en orden**: RabbitMQ primero (sin clientes aún), después worker (consume cola vacía), después API nueva (empieza a publicar). El compose `depends_on` cubre esto en dev.
3. **Rollback**: revertir el commit que cambia el handler HTTP a publicar restaura `BackgroundTasks`. La migración del `csv_blob` es aditiva y no rompe el código viejo (la columna queda NULL). RabbitMQ se puede dejar corriendo sin uso o apagar.
4. **Compatibilidad**: clientes externos no necesitan cambios. Los timestamps `started_at` van a ser un poco posteriores a antes (delay de la cola), pero siguen siendo monótonos respecto a `created_at`.

## Open Questions

- ¿`BATCH_ORPHAN_THRESHOLD_SECONDS = 600` está bien para empezar, o lo bajamos? Propongo 600 y ajustamos si vemos jobs reales tardando más en S6.
- ¿Queremos límite hard de réplicas del worker? Por ahora 1 réplica en compose; documentar que se puede escalar con `docker compose up --scale worker=3`.
- ¿Tag de la imagen RabbitMQ pin exacto (`3.13.7-management-alpine`) o `3.13-management-alpine`? Default propuesto: minor pin (`3.13-management-alpine`) — patches automáticos, breaking de minor controlado por nosotros.
