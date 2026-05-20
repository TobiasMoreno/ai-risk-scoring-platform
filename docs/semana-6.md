# Semana 6 — Observabilidad + documentación + portfolio

**Objetivo:** dejar el proyecto presentable. Instrumentar, documentar y empaquetar.

**Tag al cerrar:** `v1.0`

---

## Qué estudiar

- Logs estructurados (JSON, correlación por `request_id`).
- Métricas: counter, gauge, histogram, summary.
- Prometheus exposition format.
- Grafana dashboards.
- OpenTelemetry básico (traces).
- Las 4 golden signals (latency, traffic, errors, saturation).
- Métricas específicas de ML serving: latencia de inferencia, distribución de inputs/outputs, drift conceptual.

---

## Qué construir

### Logs estructurados

`structlog` o `logging` con formatter JSON. Cada log incluye:

- `timestamp`
- `level`
- `request_id`
- `model_version`
- `event` (qué pasó)
- `latency_ms` (cuando aplica)

### Métricas Prometheus

`prometheus-client`. Endpoint `GET /metrics` con:

- `risk_predictions_total{model_version, risk_level, source}` — counter
- `risk_prediction_latency_seconds{source}` — histogram
- `risk_prediction_errors_total{error_type}` — counter
- `risk_batch_jobs_total{status}` — counter
- `risk_batch_job_duration_seconds` — histogram
- `risk_model_inference_latency_seconds` — histogram (solo la inferencia, sin DB/red)

### Prometheus + Grafana en Compose

```yaml
prometheus:
  image: prom/prometheus
  volumes: ["./infra/prometheus.yml:/etc/prometheus/prometheus.yml"]
  ports: ["9090:9090"]

grafana:
  image: grafana/grafana
  ports: ["3000:3000"]
  volumes: [grafana-data:/var/lib/grafana]
```

### Dashboard

Provisionar al menos uno con paneles:

- Predicciones por minuto.
- Latencia p50/p95/p99.
- Tasa de errores.
- Distribución de `risk_level`.
- Jobs batch por estado.

### Documentación final

- `README.md` pulido para portfolio.
- `docs/architecture.md` actualizado con la versión final.
- `docs/decisions.md` cerrado.
- `docs/roadmap.md` con futuros pasos (drift detection, MLflow, etc.).
- Diagrama en imagen (o ASCII si alcanza).
- Demo: GIF o screenshots.

---

## Tareas

- [ ] Agregar `prometheus-client`, `structlog`, `opentelemetry-*` a `requirements.txt`.
- [ ] Logger central con JSON output + `request_id` via middleware.
- [ ] Middleware que mide latencia por endpoint.
- [ ] Endpoint `/metrics` expuesto.
- [ ] Definir e instrumentar las métricas listadas.
- [ ] `prometheus.yml` scrapeando API y worker.
- [ ] Grafana provisioning (dashboard como código).
- [ ] Tests que verifican que `/metrics` devuelve formato Prometheus válido.
- [ ] README profesional con: qué es, por qué, cómo correr, arquitectura, decisiones.
- [ ] Diagrama de arquitectura final.
- [ ] Sección "What I learned" en el README.
- [ ] Post de LinkedIn / journal del proyecto (opcional pero recomendado).
- [ ] Merge final a `main` + tag `v1.0`.

---

## Decisiones a registrar

- ¿`structlog` vs `logging` con formatter?
- ¿OpenTelemetry sí o no? (puede ser overkill para portfolio).
- ¿Dashboard provisionado en código o exportado manual?
- ¿Métricas en `/metrics` o en endpoint separado por seguridad?

Anotar en [decisions.md](decisions.md).

---

## Criterios de cierre

- `docker compose up` levanta API + worker + DB + RabbitMQ + Prometheus + Grafana.
- Hacer requests genera datos en el dashboard.
- README de portfolio claro y autocontenido.
- Diagrama de arquitectura presente.
- Decisiones documentadas.
- Tag `v1.0` creado.

---

## Preguntas para entrevista al cerrar S6

- ¿Qué métricas mirarías para detectar que el modelo se degrada?
- ¿Qué es data drift y cómo lo detectarías?
- ¿Qué loguearías de cada predicción y por qué?
- ¿Cómo investigarías una caída de p99 en producción?
- ¿Qué alertas crearías y a qué umbral?
- ¿Cómo extenderías este sistema para soportar múltiples modelos a la vez?
