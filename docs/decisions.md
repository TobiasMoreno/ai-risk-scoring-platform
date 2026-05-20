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

<!-- Próximas entradas a medida que avanzan las semanas:

## ADR-06 — ORM y patrón de acceso a datos (S3)
## ADR-07 — Procesamiento batch in-process vs worker externo (S4)
## ADR-08 — RabbitMQ vs Kafka (S5)
## ADR-09 — Sync vs async en endpoint /risk-score (S5)
## ADR-10 — structlog vs logging stdlib (S6)
## ADR-11 — OpenTelemetry sí o no (S6)

-->
