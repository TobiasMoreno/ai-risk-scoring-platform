## Why

El repositorio sólo contiene documentación; no existe código ejecutable todavía. Semana 1 del roadmap exige levantar la base del servicio: una API FastAPI con endpoints mock que sirva de andamio para iteraciones posteriores (modelo real, persistencia, observabilidad). Sin esta base no se puede avanzar al resto del roadmap.

## What Changes

- Crear estructura de paquete `app/` (main, config, api/routes, schemas, services) y `tests/`.
- Exponer `GET /health` que devuelve `{"status": "ok"}`.
- Exponer `POST /risk-score` con validación Pydantic y lógica **mock**: `risk_score = clip(debt / income, 0, 1)`, bucketizado en `low` (<0.33), `medium` (<0.66), `high` (resto). Respuesta incluye `request_id` (UUID), `risk_score`, `risk_level`, `model_version`.
- Exponer `GET /predictions/{id}` como stub (501 Not Implemented o mock fijo) — placeholder para persistencia futura.
- Añadir `requirements.txt` con FastAPI, uvicorn, pydantic, pydantic-settings, pytest, httpx.
- Añadir `Dockerfile` reproducible para construir la imagen `risk-api`.
- Añadir tests con `httpx.AsyncClient`: happy path de `/risk-score`, 422 por input inválido, health, stub de `/predictions/{id}` (≥5 tests).
- Actualizar `README.md` con instrucciones de setup / run / test / docker.

## Capabilities

### New Capabilities
- `risk-scoring-api`: superficie HTTP del servicio — health check, scoring sincrónico (mock por ahora) y lookup de predicciones por id. Define contratos de request/response y comportamiento de validación; la implementación del scoring es intercambiable (mock → modelo real en semanas siguientes).

### Modified Capabilities
<!-- Ninguna: no existen specs previas. -->

## Impact

- **Código nuevo**: árbol `app/` y `tests/` desde cero.
- **Dependencias**: FastAPI, uvicorn[standard], pydantic v2, pydantic-settings, pytest, httpx, anyio (transitivo).
- **Build**: nuevo `Dockerfile` (base `python:3.11-slim`).
- **CI**: aún no se configura — sólo se exige `pytest` local verde.
- **Compatibilidad**: ninguna (greenfield). El contrato de `/risk-score` se considera estable a nivel de shape; el algoritmo interno cambiará cuando entre el modelo real (no será breaking si el shape se respeta).
- **Tag al cerrar**: `v0.1`.
