# Decisiones técnicas (ADR-lite)

Bitácora de decisiones. Una entrada por decisión. Formato simple, sin ceremonia.

Template:

```md
## ADR-NN — Título corto

- **Fecha**: YYYY-MM-DD
- **Semana**: SN
- **Estado**: propuesta | aceptada | reemplazada por ADR-NN

### Contexto
Qué problema o pregunta motivó la decisión.

### Opciones consideradas
- A: ...
- B: ...
- C: ...

### Decisión
Elegí X.

### Razón
Por qué X gana contra las alternativas. Trade-offs aceptados.

### Consecuencias
- Lo que habilita.
- Lo que limita o complica.
- Qué revisar en el futuro.
```

---

## ADR-01 — Lenguaje principal: Python

- **Fecha**: 2026-05-20
- **Semana**: S1
- **Estado**: aceptada

### Contexto
La base profesional es Java/Spring Boot. Hay que elegir el lenguaje principal para este proyecto orientado a AI/ML Platform.

### Opciones consideradas
- A: Java/Spring Boot (lo que ya manejo).
- B: Python (FastAPI).
- C: Go.

### Decisión
Python con FastAPI.

### Razón
- Es el lenguaje dominante en ecosistemas AI/ML.
- Scikit-learn, pandas, librerías de ML están en Python.
- FastAPI da buena DX y OpenAPI gratis.
- Mostrar capacidad de operar fuera de mi stack base es parte del objetivo del proyecto.

### Consecuencias
- Curva de aprendizaje inicial.
- Habilita usar el ecosistema ML nativo.
- Java queda como fortaleza paralela en CV, no como stack de este proyecto.

---

## ADR-02 — Algoritmo del modelo: LogisticRegression

- **Fecha**: 2026-05-20
- **Semana**: S2
- **Estado**: aceptada

### Contexto
S2 reemplaza el scoring mock por un modelo Scikit-learn. Hay que elegir un algoritmo para el primer iter.

### Opciones consideradas
- A: `LogisticRegression`.
- B: `RandomForestClassifier`.
- C: Gradient boosting (XGBoost / LightGBM).

### Decisión
A — `LogisticRegression` dentro de un `Pipeline(StandardScaler, LogisticRegression)`.

### Razón
- Es el "hola mundo" de clasificación; coeficientes/sigmoide/regularización se explican fácil en entrevista.
- `predict_proba` calibrado de fábrica; RF requiere calibración extra para probabilidades honestas.
- El dataset sintético es lineal-friendly; RF/GBT serían overkill.
- Latencia mínima al servir; modelo pesa KBs.

### Consecuencias
- Suficiente para la mecánica de S2 (entrenar → serializar → cargar).
- Si en S3+ se cambia el dataset por uno no-lineal, habrá que revisar la decisión.
- Migrar a RF/GBT más adelante sólo cambia el step `clf` del pipeline — sin tocar la API.

---

## ADR-03 — Dataset: sintético en lugar de público

- **Fecha**: 2026-05-20
- **Semana**: S2
- **Estado**: aceptada

### Contexto
Necesito un dataset para S2 que tenga las features fijadas por el contrato (`income`, `age`, `debt`, `employment_years`).

### Opciones consideradas
- A: Generar dataset sintético en `train_model.py` con reglas + ruido.
- B: Descargar dataset público (German Credit, UCI Adult, etc.) y mapear columnas.

### Decisión
A — `make_dataset()` genera 5000 filas con `numpy.random` seed fija.

### Razón
- Cero dependencias de red/descarga ni encoding categórico.
- Reproducible byte-a-byte con `seed=42`.
- Las features ya coinciden con el contrato HTTP; no hay mapeo.
- El objetivo de S2 es la mecánica, no el realismo.

### Consecuencias
- El modelo no tiene valor predictivo real — señalizado en README y `model_version="v0.2.0"`.
- Cuando importe realismo (futuro), reemplazar `make_dataset()` no afecta a `ModelService`.

---

## ADR-04 — Thresholds de risk_level: 0.33 / 0.66

- **Fecha**: 2026-05-20
- **Semana**: S2
- **Estado**: aceptada

### Contexto
`risk_score` ∈ [0, 1] necesita bucketizar a `low | medium | high`.

### Opciones consideradas
- A: Umbrales fijos uniformes (0.33 / 0.66).
- B: Umbrales ajustados a la distribución observada en test (cuantiles).
- C: Umbrales por métrica de negocio (precisión a recall fijo).

### Decisión
A — `< 0.33` → low, `< 0.66` → medium, resto → high. Mismos umbrales que S1 (mock).

### Razón
- Permite comparar S1 vs S2 con la misma escala de bucketing.
- Sin métrica de negocio definida todavía, B/C son prematuros.
- Vive en `ModelService.predict()`, fácil de mover sin retrain.

### Consecuencias
- Distribución de buckets puede quedar sesgada según el modelo — aceptable.
- Revisar en S6 cuando entren métricas de negocio/observabilidad.

---

## ADR-05 — Carga del modelo: fail-fast en startup

- **Fecha**: 2026-05-20
- **Semana**: S2
- **Estado**: aceptada

### Contexto
¿Qué hace el servicio si el `.joblib` no existe o está corrupto al arrancar?

### Opciones consideradas
- A: Fail-fast: `lifespan` re-raisea, uvicorn no termina de levantar.
- B: Carga perezosa: primer request intenta cargar; falla 500 si no puede.
- C: Modo degradado: arranca, responde 503 a `/risk-score` hasta que el modelo cargue.

### Decisión
A — fail-fast en startup. Binario `gitignored`; README documenta `python -m app.models.train_model` antes de `uvicorn`.

### Razón
- Errores tempranos son baratos; servir 500s en producción es caro.
- La carga es O(KB) → no hay razón para hacerla perezosa.
- Modo degradado tiene sentido cuando hay tráfico real y SLOs — no en S2.

### Consecuencias
- Clone fresco sin binario no arranca → trade-off aceptado vs commitear binarios en git.
- Cuando entre model registry / hot reload (futuro), revisar política.

---

## ADR-06 — SQLAlchemy 2.x **sync**

- **Fecha**: 2026-05-20
- **Semana**: S3
- **Estado**: aceptada

### Contexto
S3 introduce PostgreSQL. SQLAlchemy 2.x ofrece API sync (clásica) y async (con `asyncpg`).

### Opciones consideradas
- A: Sync (`psycopg` v3 + sessionmaker).
- B: Async (`asyncpg` + AsyncSession).

### Decisión
A — sync.

### Razón
- Async exige que **todo** el stack sea async (engine, session, repo, service, routers). Mucho más código y más cuidado al testear.
- FastAPI corre rutas sync en threadpool — válido y seguro.
- A 10–100 RPS contra DB local, sync no es cuello de botella.
- Repository pattern aísla un cambio futuro a async.

### Consecuencias
- Threads del pool pueden bloquearse en queries lentas — aceptable mientras no haya métricas que digan lo contrario.
- Migrar a async, si se necesita, queda localizado en `db/database.py` y `repositories/`.

---

## ADR-07 — `JSONB` para input_payload y prediction

- **Fecha**: 2026-05-20
- **Semana**: S3
- **Estado**: aceptada

### Contexto
La tabla `prediction_requests` guarda lo que entró y lo que salió. Hay que elegir entre columnas tipadas (`income REAL`, `risk_score REAL`, etc.) o JSONB.

### Opciones consideradas
- A: JSONB para `input_payload` y `prediction`.
- B: Columnas tipadas para cada campo.
- C: Mezcla — columnas para campos consultables, JSONB para extras.

### Decisión
A — JSONB para ambos blobs.

### Razón
- El modelo va a evolucionar: S4 puede sumar features, S5 puede sumar metadata. JSONB absorbe sin migración.
- Queries actuales filtran por `request_id`, `created_at`, `model_version` (ya columnas) y `risk_level` (extraído de `prediction->>'risk_level'`).
- Si en algún momento `risk_level` pesa, índice GIN o columna calculada.

### Consecuencias
- Sin tipado fuerte para el contenido del JSON — el contrato lo da Pydantic en la API.
- Queries que filtren por contenido del JSON requieren índices ad-hoc cuando duela.

---

## ADR-08 — Repository pattern entre services y SQLAlchemy

- **Fecha**: 2026-05-20
- **Semana**: S3
- **Estado**: aceptada

### Contexto
Servicios pueden hablar SQLAlchemy directo o pasar por una capa repository.

### Opciones consideradas
- A: Repository (`PredictionRepository` expone métodos de dominio).
- B: Service ↔ Session directo.

### Decisión
A — repository.

### Razón
- Servicios mockean trivialmente el repo en tests unitarios.
- Tests del repo van contra DB real, una sola vez.
- Aísla el cambio sync → async (si llega) y el cambio de ORM (improbable pero posible).

### Consecuencias
- Una capa más en cada feature.
- Boilerplate aceptado a cambio de testabilidad y aislamiento.

---

## ADR-09 — PK: `BIGSERIAL id` + `UUID request_id UNIQUE`

- **Fecha**: 2026-05-20
- **Semana**: S3
- **Estado**: aceptada

### Contexto
La tabla necesita un PK estable y un identificador externo para el cliente.

### Opciones consideradas
- A: PK `BIGSERIAL` + `request_id UUID UNIQUE`.
- B: PK `UUID` (v4 o v7).
- C: PK compuesto.

### Decisión
A — `id BIGSERIAL` PK, `request_id UUID UNIQUE`.

### Razón
- `BIGSERIAL` ordena por inserción, 8 bytes, ideal para paginado por keyset.
- `request_id UUID` es el identificador externo (cliente, logs, correlación).
- Lookups por `request_id` son rápidos vía UNIQUE.

### Consecuencias
- Dos índices BTREE pequeños.
- Si en el futuro se quiere keyset pagination con UUID v7 ordenable, hay opción de migrar — pero no es necesario.

---

<!-- Próximas entradas a medida que avanzan las semanas:

## ADR-10 — Procesamiento batch in-process vs worker externo (S4)
## ADR-11 — RabbitMQ vs Kafka (S5)
## ADR-12 — Sync vs async en endpoint /risk-score (S5)
## ADR-13 — structlog vs logging stdlib (S6)
## ADR-14 — OpenTelemetry sí o no (S6)

-->
