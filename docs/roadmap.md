# Roadmap + checklist consolidado

Vista única de progreso a lo largo de las 6 semanas + extensiones futuras.

---

## Roadmap

```
Semana 1  →  Python + FastAPI + endpoints mock                       (v0.1)
Semana 2  →  Modelo Scikit-learn + inferencia real                   (v0.2)
Semana 3  →  PostgreSQL + historial + métricas básicas               (v0.3)
Semana 4  →  Jobs batch + procesamiento de CSV                       (v0.4)
Semana 5  →  Mensajería + worker asincrónico                         (v0.5)
Semana 6  →  Observabilidad + documentación + portfolio              (v1.0)
```

Detalle por semana en [semana-1.md](semana-1.md) → [semana-6.md](semana-6.md).

---

## Checklist de progreso

### Fundamentos

- [ ] Entiendo training vs inference.
- [ ] Entiendo batch vs online prediction.
- [ ] Entiendo qué es model serving.
- [ ] Entiendo qué hace un AI/ML Platform Engineer.
- [ ] Puedo explicar el rol sin venderme como Data Scientist.

### Python / API

- [ ] Puedo crear una API con FastAPI.
- [ ] Puedo validar requests con Pydantic.
- [ ] Puedo escribir tests con Pytest.
- [ ] Puedo dockerizar la API.
- [ ] Puedo documentar endpoints con OpenAPI.

### ML básico

- [ ] Puedo entrenar un modelo simple con Scikit-learn.
- [ ] Puedo guardar un modelo con Joblib.
- [ ] Puedo cargar el modelo desde una API.
- [ ] Puedo devolver una predicción.
- [ ] Puedo versionar el modelo.

### Datos

- [ ] Puedo guardar predicciones en PostgreSQL.
- [ ] Puedo consultar historial.
- [ ] Puedo hacer queries agregadas.
- [ ] Entiendo BigQuery conceptualmente.
- [ ] Entiendo diferencia OLTP vs OLAP.

### Batch / mensajería

- [ ] Puedo crear un batch job.
- [ ] Puedo procesar un CSV.
- [ ] Puedo usar una cola.
- [ ] Puedo crear un worker.
- [ ] Puedo manejar reintentos e idempotencia.

### Observabilidad

- [x] Tengo logs estructurados.
- [x] Tengo métricas de latencia.
- [x] Tengo métricas de errores.
- [x] Tengo métricas de cantidad de predicciones.
- [x] Tengo dashboard básico.
- [ ] Puedo explicar cómo investigaría un problema en producción.

### Portfolio

- [x] README profesional.
- [x] Diagrama de arquitectura.
- [x] Decisiones técnicas documentadas.
- [x] Trade-offs explícitos.
- [x] Tests.
- [x] Docker Compose.
- [x] Demo local funcionando.
- [ ] Post de LinkedIn / journal explicando el proyecto.

---

## Extensiones futuras (post-v1.0)

Cosas que no entran en las 6 semanas pero serían el siguiente paso. Útiles si el proyecto se quiere extender o como temas para mencionar en entrevista ("lo siguiente que haría sería...").

### Model lifecycle
- [ ] MLflow para tracking de experimentos + model registry.
- [ ] Shadow deployment de nueva versión.
- [ ] Canary deployment con feature flags.
- [ ] A/B testing de modelos.

### Datos
- [ ] Feature store básico (incluso solo conceptual, con tabla `features`).
- [ ] Pipeline con Airflow o Prefect para re-entrenamiento.
- [ ] Validación de datos con Great Expectations o Pandera.
- [ ] Sincronización a BigQuery para análisis.

### Observabilidad avanzada
- [ ] OpenTelemetry con collector y trazas API → RabbitMQ → worker.
- [ ] Alertas Prometheus/Grafana para p95, error rate y backlog.
- [ ] Detección de data drift con `evidently` o métricas custom.
- [ ] Alertas en Grafana con notificación.
- [ ] Tracing distribuido completo con OpenTelemetry.
- [ ] Endpoint de health más profundo (modelo cargado, DB OK, cola OK).

### Escalabilidad
- [ ] Cache de predicciones para inputs repetidos.
- [ ] Worker con autoscaling.
- [ ] Particionado de la tabla `prediction_requests`.
- [ ] Read replicas para queries de análisis.

### Seguridad
- [ ] Auth con API key o JWT.
- [ ] Rate limiting.
- [ ] Audit log de quién consultó qué.
- [ ] Sanitización y límites en uploads de CSV.

### GenAI (puente a otros proyectos)
- [ ] Endpoint que explica una predicción usando un LLM.
- [ ] Resumen de jobs batch generado por LLM.
- [ ] Análisis automático de patrones en predicciones recientes.

---

## Criterio de "estoy listo para aplicar"

Cuando pueda:

- Explicar qué hace un Backend Engineer en AI/ML Platform.
- Construir una API que sirva un modelo.
- Procesar predicciones batch.
- Usar una cola con worker.
- Guardar historial y resultados.
- Medir latencia, errores y volumen.
- Documentar arquitectura y trade-offs.
- Defender el proyecto en una entrevista de 1h.
- Conectar mi experiencia backend actual con IA/ML en producción.
