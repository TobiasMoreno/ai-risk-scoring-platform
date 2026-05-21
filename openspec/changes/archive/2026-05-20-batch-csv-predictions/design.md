## Context

S3 dejó persistencia + endpoints de consulta. S4 quiere subir un CSV y obtener predicciones en lote. El roadmap es explícito: en S4 el procesamiento corre dentro del proceso de la API (BackgroundTasks); en S5 se mueve a un worker externo con cola. Por eso, las decisiones aquí deben elegir la opción **simple** pero dejar el modelo de datos y la API "worker-ready": un consumidor del status no debería notar la diferencia cuando el procesamiento migre fuera del proceso.

## Goals / Non-Goals

**Goals:**
- Subir un CSV chico/mediano (≤10 MB por default) y obtener un `job_id` inmediatamente.
- State machine clara y observable vía `GET /batch-predictions/{job_id}`.
- Idempotencia por `external_id` dentro de un mismo job (re-subir mismo CSV no duplica).
- Filas inválidas no rompen el job entero — `failed` cuenta separado de `processed`.
- Resultados consultables por job.

**Non-Goals:**
- Cola, worker externo, retries con backoff. Eso es S5.
- Job runner concurrente para varios jobs en paralelo dentro del proceso. Por ahora un BackgroundTask por job; si entran 10 a la vez, los 10 corren en threadpool de FastAPI — aceptable.
- Streaming del CSV de vuelta (`results` paginado por offset alcanza).
- Webhooks / SSE / push del status. Polling por GET.
- Validar contenido semántico del CSV (negocio) más allá del schema Pydantic.
- Multi-tenant, autenticación, rate limiting (siguen postergados).

## Decisions

### 1. Procesamiento in-proceso con `BackgroundTasks`
- FastAPI ofrece `BackgroundTasks` para tareas que corren después de devolver la response, en el mismo proceso/event loop. Para S4 alcanza: no hay tráfico real.
- El `BackgroundTask` ejecuta una función sync que toma `job_id` y delega en `BatchService.process_job(job_id)`. Esa función abre **su propio engine/session** (no la session del request, que ya se cerró).

**Alternativa descartada:** `asyncio.create_task` directamente — `BackgroundTasks` ya hace el handling de exceptions/cleanup correcto.

### 2. CSV con `csv.DictReader` (no pandas)
- pandas pesa MB y es overkill para 4 columnas. `csv` stdlib alcanza, no asume tipos (Pydantic los infiere).
- Lectura row-by-row → memoria O(chunk_size), no O(N).

### 3. Chunks de 1000 filas, configurable
- Cada chunk = una transacción. Permite progreso visible y aislamiento de fallos.
- 1000 es heurística: con 4 columnas, ~50 KB por chunk → trivial. Configurable via `Settings.batch_chunk_size` por si tira para arriba en el futuro.

### 4. Idempotencia: UNIQUE parcial `(job_id, external_id)`
- Constraint en DB es la fuente de verdad. El servicio intenta `INSERT`; si choca con el UNIQUE, lo cuenta como "skipped" (no `failed`).
- Implementación: `INSERT ... ON CONFLICT (job_id, external_id) DO NOTHING` vía SQLAlchemy `insert(...).on_conflict_do_nothing()` (dialecto Postgres). El repo expone `save_batch_row(...)` que devuelve `True` si insertó, `False` si fue conflict.
- Reprocesar el mismo CSV (mismo `job_id`) NO crea filas duplicadas. Reprocesar el mismo CSV con un `job_id` distinto sí duplica — porque el UNIQUE es por job, no global. Decisión consciente.

**Alternativa descartada:** UNIQUE global por `external_id`. Bloquea casos legítimos (el mismo external_id puede aparecer en jobs distintos por diferentes equipos / contextos).

### 5. UNIQUE parcial (no full)
- `external_id` y `job_id` son nullable: requests online no los tienen.
- Constraint completo `UNIQUE (job_id, external_id)` permitiría sólo una fila con `(NULL, NULL)` en algunos motores. En Postgres NULL ≠ NULL en UNIQUE, así que online "funciona", pero un UNIQUE parcial `WHERE job_id IS NOT NULL AND external_id IS NOT NULL` deja explícita la intención y evita sorpresas.

### 6. Política de filas inválidas: skip + count
- Validación: Pydantic en `RiskScoreRequest` (mismas reglas que el endpoint online).
- Fila inválida → `failed += 1`, log con el número de línea + razón, continuar.
- Cero opción de "fail-fast" en S4. Si en algún momento aparece "necesito fail-fast para validar el archivo entero antes de empezar", se agrega un `?dry_run=true` que sólo cuenta.

### 7. Semántica de `status`
- `PENDING`: creado, BackgroundTask aún no arrancó (raro: hay una ventana mínima entre crear job y empezar a procesar).
- `PROCESSING`: BackgroundTask en curso. `started_at` set.
- `COMPLETED`: terminó y `processed > 0`. `finished_at` set.
- `FAILED`: terminó y `processed == 0` y `total_records > 0`. `finished_at` set. Esto distingue "todas fallaron" vs "algunas fallaron".
- Job con `total_records = 0` (CSV vacío): `COMPLETED` con todo en 0. Más amigable que `FAILED`.

### 8. Validación del CSV al ingresar
- Headers requeridos: `income,age,debt,employment_years`. `external_id` opcional.
- Si faltan headers requeridos → `422 Unprocessable Entity` antes de crear el job.
- `total_records` = filas leídas (sin contar headers). Esto requiere una lectura preliminar — para CSV ≤10MB, aceptable.

### 9. Tamaño máximo de upload
- Default `10 MB`. Si excede, `413 Payload Too Large` antes de tocar disco.
- Implementación: leer en streaming desde `UploadFile.read(max_bytes + 1)` y comparar. Alternativa más sucia: `Content-Length` (no siempre presente; no confiable).

### 10. Servicio: dos pasos separables
- `BatchService.create_job(stream, source) -> BatchJob` valida headers, cuenta filas, devuelve el job con `PENDING`. **No** procesa.
- `BatchService.process_job(job_id, stream)` corre la lógica. En S4 lo invoca `BackgroundTasks` pasando los **bytes del archivo** preservados en memoria (porque `UploadFile` es streaming y `BackgroundTask` corre después de cerrarlo). En S5, lo invoca el worker con un puntero (object storage o similar).
- Trade-off S4: el archivo entero queda en memoria del proceso de la API mientras se procesa. Con 10 MB es aceptable.

### 11. Resultados: query con filtro
- `GET /batch-predictions/{job_id}/results` reusa el repo de `prediction_requests` con filtro `WHERE job_id = ?`, paginado.
- Misma forma de respuesta que `GET /predictions/{id}`/`GET /predictions` para ahorrar schemas.

### 12. Migración Alembic
- Nueva revisión que crea `batch_jobs`, agrega `job_id` y `external_id` a `prediction_requests`, y agrega el índice único parcial.
- `downgrade()` revierte: drop index, drop columns, drop table.

### 13. Logging
- Cada chunk: `INFO chunk=<n> processed=<x> failed=<y>`.
- Fin del job: `INFO job=<id> status=<...> total=<...> processed=<...> failed=<...>`.

## Risks / Trade-offs

- **Procesamiento bloquea threadpool**: cierto. Un job grande puede degradar la latencia online. Mitigación: tamaño máximo + chunks chicos; S5 lo resuelve definitivamente.
- **Proceso crashea a mitad**: jobs quedan en `PROCESSING` para siempre. No hay reaper. Aceptable para S4 (local + corta vida); S5 lo arregla con heartbeat.
- **`BackgroundTask` vive en el proceso**: si reinician uvicorn, jobs in-flight se pierden. Documentado en decisions; resuelto en S5.
- **Idempotencia parcial**: distintos `job_id` con mismo `external_id` no se dedup entre jobs. Decisión consciente.
- **PII**: el CSV puede traer `external_id` que sea PII (DNI, email, etc.). Para v0.4 no se hashea — README pide datos sintéticos.

## Migration Plan

- `alembic upgrade head` aplica la nueva revisión. Compatibilidad con datos existentes: las columnas nuevas son nullable; el constraint es parcial.
- Rollback: `alembic downgrade -1`.
- Clientes: `POST /risk-score` sigue funcionando idéntico. Aparecen 3 endpoints nuevos.

## Open Questions

- ¿Vale un endpoint `GET /batch-predictions?limit=` para listar todos los jobs? Posponer; con `job_id` alcanza.
- ¿Permitimos cancelar un job? Posponer; en S4 no hay forma limpia in-process.
- ¿Devolver `Location: /batch-predictions/{job_id}` en el `202`? Sí, gratis.
