# Glosario AI/ML aplicado a Platform

Términos que tengo que poder usar sin titubear en entrevistas.

---

## Modelado

**Training** — etapa donde el modelo aprende patrones a partir de datos históricos. Produce un artefacto (archivo serializado).

**Inference** — usar el modelo ya entrenado para generar una predicción sobre datos nuevos.

**Dataset** — conjunto de datos. Generalmente se divide en train / validation / test.

**Feature** — variable de entrada al modelo. Ej: `income`, `age`.

**Target / label** — lo que el modelo intenta predecir.

**Feature engineering** — transformar datos crudos en features útiles para el modelo (escalado, encoding, agregaciones).

**Feature store** — sistema que centraliza definición y cómputo de features para reusarlas entre training e inference. Evita el "skew train/serve".

**Overfitting** — el modelo memoriza el train set y generaliza mal a datos nuevos.

**Underfitting** — el modelo es demasiado simple y no captura los patrones.

---

## Tipos de predicción

**Clasificación** — el output es una clase discreta (low / medium / high).

**Regresión** — el output es un número continuo (un score, un precio).

**Online prediction** — predicción en tiempo real, una request a la vez, baja latencia.

**Batch prediction** — predicciones masivas en proceso programado, alta latencia tolerada.

---

## Métricas de evaluación

**Accuracy** — porcentaje de predicciones correctas. Engañosa con clases desbalanceadas.

**Precision** — de las que predije como positivas, cuántas lo eran. Importa cuando un falso positivo es caro.

**Recall** — de las realmente positivas, cuántas detecté. Importa cuando un falso negativo es caro.

**F1** — media armónica de precision y recall.

**Confusion matrix** — tabla TP / FP / TN / FN.

**AUC-ROC** — qué tan bien el modelo separa clases a distintos thresholds.

---

## Producción / Platform

**Model serving** — exponer un modelo como servicio consumible (típicamente API).

**Model versioning** — cada modelo entrenado tiene una versión inmutable. La response incluye `model_version` para trazabilidad.

**Model registry** — catálogo de modelos versionados con metadata (métricas, fecha, dataset). Ej: MLflow.

**Rollback** — volver a una versión previa del modelo si la nueva degrada.

**Canary / shadow deployment** — desplegar la versión nueva en paralelo (sombra) o a un % de tráfico (canary) antes de promoverla.

**A/B testing de modelos** — comparar performance de dos modelos sirviendo tráfico real.

---

## Datos

**ETL** — Extract / Transform / Load. Pipeline clásico.

**ELT** — Extract / Load / Transform. Más común con data warehouses modernos.

**OLTP** — Online Transaction Processing. Bases transaccionales (PostgreSQL). Optimizadas para muchas escrituras pequeñas.

**OLAP** — Online Analytical Processing. Bases analíticas (BigQuery, Redshift). Optimizadas para queries grandes sobre mucha data.

**Data lake** — almacenamiento crudo de datos sin estructura impuesta (S3, GCS).

**Data warehouse** — almacenamiento estructurado optimizado para análisis (BigQuery, Snowflake, Redshift).

**Data lakehouse** — híbrido (Delta Lake, Iceberg).

**Data drift** — distribución de los inputs cambia con el tiempo respecto a training.

**Concept drift** — la relación entre inputs y target cambia con el tiempo.

**Data quality** — completitud, validez, consistencia, frescura, unicidad.

---

## Observabilidad

**Las 4 golden signals** — latency, traffic, errors, saturation.

**p50 / p95 / p99** — percentiles de latencia. p99 es el peor 1%.

**SLI / SLO / SLA** — indicador, objetivo, acuerdo.

**Trace / span** — recorrido de una request a través de servicios.

**Structured logging** — logs en JSON con campos consultables.

**Cardinality** (en métricas) — número de combinaciones únicas de labels. Alta cardinalidad rompe Prometheus.

---

## Mensajería

**Producer / consumer** — publica / consume mensajes.

**Topic / queue** — destino del mensaje.

**Ack / nack** — confirmación o rechazo del consumer.

**DLQ (Dead Letter Queue)** — cola donde van los mensajes que fallaron repetidas veces.

**At-least-once** — el mensaje se entrega al menos una vez. Puede duplicarse.

**At-most-once** — el mensaje se entrega como mucho una vez. Puede perderse.

**Exactly-once** — el mensaje se entrega exactamente una vez. Caro de garantizar.

**Idempotencia** — procesar el mismo mensaje N veces produce el mismo resultado que procesarlo 1 vez.

---

## GenAI (para los proyectos secundarios)

**LLM (Large Language Model)** — modelo de lenguaje grande (GPT, Claude, Llama).

**Embedding** — representación vectorial de un texto que captura su significado.

**Vector database** — DB optimizada para búsqueda por similitud de vectores (pgvector, Pinecone, Weaviate, Qdrant).

**RAG (Retrieval-Augmented Generation)** — recuperar contexto relevante + generar respuesta con un LLM.

**Chunking** — partir documentos grandes en fragmentos para indexar.

**Prompt engineering** — diseñar el prompt para maximizar calidad de respuesta.

**Grounding** — anclar la respuesta del LLM a fuentes verificables.

**Hallucination** — el LLM inventa contenido. RAG la mitiga, no la elimina.

**Fine-tuning** — re-entrenar un modelo base con datos propios.

**Tool use / function calling** — el LLM decide invocar funciones externas como parte de la respuesta.
