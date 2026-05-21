# Semana 4 — Jobs batch + CSV

**Objetivo:** procesar predicciones por lotes desde CSV, con estado de job, reintentos e idempotencia.

**Tag al cerrar:** `v0.4`

---

## Qué estudiar

- Procesamiento batch vs streaming.
- Estados de job (state machine): `PENDING → PROCESSING → COMPLETED / FAILED`.
- Idempotencia: por qué importa, cómo lograrla.
- Reintentos con backoff.
- Manejo de errores parciales (un registro falla, el resto sigue).
- Lectura de CSV con `pandas` o `csv` stdlib + chunks para no cargar todo a memoria.
- BackgroundTasks de FastAPI (sin cola todavía).

---

## Qué construir

### Tabla `batch_jobs`

Ver [architecture.md](architecture.md#modelo-de-datos-s3).

### Endpoints

```
POST /batch-predictions
     ↳ multipart CSV, devuelve { job_id, status: "PENDING" }
GET  /batch-predictions/{job_id}
     ↳ estado del job + progreso (processed/total)
GET  /batch-predictions/{job_id}/results
     ↳ predicciones generadas, paginadas
```

### Procesamiento

Por ahora **dentro del proceso de la API** usando `BackgroundTasks` o `asyncio.create_task`. En S5 se migra a worker externo.

Flujo:

1. API recibe CSV → guarda job con `PENDING` + cuenta filas → devuelve `job_id`.
2. Background task lee CSV en chunks → por cada fila: predice + guarda + incrementa `processed`.
3. Si falla una fila: incrementa `failed`, sigue.
4. Al final: estado `COMPLETED` (o `FAILED` si todas fallaron).

### Idempotencia

- Cada CSV puede incluir un `external_id` por fila.
- Persistir `(job_id, external_id)` único.
- Re-procesar el mismo job no duplica predicciones.

---

## Tareas

- [x] Migración Alembic: tabla `batch_jobs` + columna `external_id` en `prediction_requests`.
- [x] `BatchService` con `create_job`, `process_job`, `get_status`, `get_results`.
- [x] Endpoint POST con `UploadFile`.
- [x] BackgroundTask que procesa.
- [x] Tests con CSV de ejemplo (happy path + filas inválidas + reintento idempotente).
- [x] CSV de ejemplo en `tests/fixtures/` (y `samples/` para el README).
- [x] Documentar formato esperado del CSV.
- [ ] Commit + tag `v0.4`.

---

## Decisiones a registrar

- ¿Procesamiento en-proceso o ya separar worker? (la ruta sugiere en-proceso ahora, worker en S5).
- ¿Tamaño de chunk para leer CSV?
- ¿Qué hacer con filas inválidas: skip, fail-fast, o ambas según severidad?
- ¿Cómo represento "job fallido pero con algunos resultados"?

Anotar en [decisions.md](decisions.md).

---

## Criterios de cierre

- Subir un CSV con N filas → genera N predicciones persistidas.
- Consultar estado muestra progreso real.
- Re-subir el mismo CSV con mismos `external_id` no duplica.
- Filas inválidas no rompen el job entero.
- Tests cubren happy path + parcial + idempotencia.

---

## Preguntas para entrevista al cerrar S4

- ¿Cómo procesarías 10M de registros sin cargarlos en memoria?
- ¿Cómo garantizás idempotencia en un endpoint batch?
- ¿Qué hacés si un job se cae en el medio?
- ¿Cómo expondrías progreso al cliente: polling, SSE, webhook?
- ¿En qué momento moverías el procesamiento fuera del proceso de la API y por qué?
