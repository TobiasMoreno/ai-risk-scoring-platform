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

<!-- Próximas entradas a medida que avanzan las semanas:

## ADR-02 — Algoritmo del modelo (S2)
## ADR-03 — ORM y patrón de acceso a datos (S3)
## ADR-04 — Procesamiento batch in-process vs worker externo (S4)
## ADR-05 — RabbitMQ vs Kafka (S5)
## ADR-06 — Sync vs async en endpoint /risk-score (S5)
## ADR-07 — structlog vs logging stdlib (S6)
## ADR-08 — OpenTelemetry sí o no (S6)

-->
