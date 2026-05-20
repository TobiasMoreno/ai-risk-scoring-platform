# Preparación de entrevista

Banco de preguntas + respuestas base. Para usar en entrevistas para roles **Backend Engineer - AI/ML Platform / GenAI / ML Platform**.

---

## Posicionamiento

**¿Cuál es tu interés en AI/ML Platform?**

> Me interesa la intersección entre backend, datos e inteligencia artificial. No busco empezar por investigación o entrenamiento avanzado de modelos, sino por construir los sistemas que permiten que esos modelos funcionen en producción: APIs, pipelines, jobs, mensajería, observabilidad y escalabilidad.

**¿Qué valor traés desde backend?**

> Diseño de APIs, integraciones, arquitectura escalable, resiliencia, observabilidad y buenas prácticas. En AI/ML eso se traduce en disponibilizar modelos de forma confiable, medirlos, monitorearlos y conectarlos con flujos reales de negocio.

**¿Por qué este proyecto?**

> Quería un ejemplo concreto que junte todo: API de inferencia, persistencia, batch, cola con worker y observabilidad. Lo construí semana por semana, cerrando cada etapa con un tag y documentando decisiones.

---

## Sobre el rol

- ¿Cuál es la diferencia entre entrenar un modelo y servirlo?
- ¿Qué significa disponibilizar un modelo en producción?
- ¿Cómo diseñarías una API para consumir un modelo?
- ¿Qué riesgos tiene un modelo en producción?
- ¿Cómo monitorearías un endpoint de inferencia?

---

## Backend / sistemas

- ¿Cómo manejarías latencia alta en un endpoint predictivo?
- ¿Qué harías si el modelo tarda demasiado?
- ¿Cómo diseñarías reintentos?
- ¿Cómo evitarías duplicar procesamiento?
- ¿Cómo aplicarías idempotencia?
- ¿Cómo versionarías un modelo?
- ¿Cómo harías rollback de un modelo?

### Respuesta base — llevar un modelo a producción

> Primero definiría el contrato de entrada y salida. Después lo expondría mediante una API o worker según si la inferencia es online o batch. Agregaría validaciones, versionado, logs estructurados, métricas de latencia y errores, trazabilidad por request, y monitoreo del comportamiento del modelo. También dejaría preparada una estrategia de rollback si una nueva versión degrada el rendimiento.

### Respuesta base — proceso batch

> Separaría la recepción del archivo del procesamiento real. La API crearía un job con estado inicial y publicaría eventos en una cola. Un worker consumiría esos mensajes para ejecutar inferencias, guardar resultados y actualizar el estado. Agregaría reintentos, idempotencia por `external_id`, control de errores y métricas del tiempo total del job.

---

## Datos

- ¿Qué diferencia hay entre una base transaccional y una analítica?
- ¿Para qué usarías BigQuery?
- ¿Qué es un pipeline de datos?
- ¿Cómo validarías la calidad de datos?
- ¿Cómo procesarías un CSV con millones de registros?

---

## Observabilidad

- ¿Qué logs agregarías a un endpoint de inferencia?
- ¿Qué métricas mirarías?
- ¿Qué alertas crearías y a qué umbral?
- ¿Qué es data drift? ¿Cómo lo detectarías?
- ¿Cómo investigarías una caída de performance?

### Respuesta base — métricas mínimas

> Latencia p50/p95/p99 de inferencia, requests por segundo, tasa de errores por tipo, distribución de outputs por `risk_level`, predicciones por `model_version` (para saber qué versión está sirviendo tráfico), y para batch: duración total del job + cantidad procesada vs fallida.

### Respuesta base — drift

> Drift de datos es cuando la distribución de inputs cambia respecto a training. Lo detectaría comparando estadísticas básicas (media, desvío, percentiles, histogramas) de los inputs actuales contra una baseline del dataset de entrenamiento, y alertando cuando una métrica como PSI o KS supera un umbral. Concept drift es cuando cambia la relación input-output, y requiere ground truth para detectarlo.

---

## Arquitectura

- ¿Cuándo procesamiento online vs batch?
- ¿Cuándo usarías una cola?
- ¿Cómo desacoplarías API y worker?
- ¿Qué pasa si falla el worker?
- ¿RabbitMQ o Kafka? ¿Cuándo cada uno?
- ¿Cómo escalarías el sistema 10x?

---

## Preguntas para hacerle al entrevistador

- ¿Cómo se versionan los modelos hoy en el equipo?
- ¿Cómo es el ciclo desde que un modelo se entrena hasta que sirve tráfico?
- ¿Qué herramientas usan para observabilidad de modelos?
- ¿El equipo de Platform trabaja con Data Scientists internos o con vendors?
- ¿Cómo manejan rollback de modelos?
- ¿Tienen feature store?
- ¿Cómo es la separación de responsabilidades entre Backend, ML Platform y Data Science?
