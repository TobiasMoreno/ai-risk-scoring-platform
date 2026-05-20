## Context

Greenfield: aún no hay código Python. El objetivo de S1 es dejar el andamio sobre el que se irán enchufando capacidades en semanas siguientes (modelo real, persistencia, batch, observabilidad). Las decisiones aquí no deben "atar" decisiones futuras, pero sí dejar puntos de extensión claros (servicio de scoring inyectable, settings tipadas, división por router).

## Goals / Non-Goals

**Goals:**
- API FastAPI corriendo localmente con `uvicorn app.main:app --reload`.
- Endpoints `/health`, `/risk-score`, `/predictions/{id}` con contratos Pydantic v2 documentados en `/docs`.
- Lógica de scoring **mock** aislada en un servicio para que el cambio a modelo real sea trivial.
- Tests con `httpx.AsyncClient` (≥5) ejecutables con `pytest`.
- Imagen Docker reproducible.

**Non-Goals:**
- Modelo de ML real, entrenamiento, ni feature store.
- Persistencia (DB, cache) — `GET /predictions/{id}` se implementa como stub.
- Autenticación, rate limiting, observabilidad (logs estructurados / tracing) — entran en semanas posteriores.
- CI/CD, despliegue remoto.
- Versionado semántico del contrato — sólo se fija `model_version="mock-0.1"`.

## Decisions

### 1. Estructura por capas dentro de `app/`
- `app/api/routes/`: routers FastAPI delgados; sólo orquestan request → service → response.
- `app/schemas/`: Pydantic models (request/response/DTOs).
- `app/services/`: lógica de negocio (scoring). Se inyecta vía `Depends` para poder sustituir el mock por el modelo real más adelante sin tocar routers.
- `app/config.py`: `Settings` con `pydantic-settings` (lee `.env`).

**Alternativa descartada:** un único `main.py` plano. Demasiado rígido para crecer.

### 2. Pydantic v2 (no v1)
La última versión es estándar de facto y FastAPI ≥0.100 lo soporta nativamente. Evita migraciones futuras.

### 3. Algoritmo mock
```
ratio = debt / income
risk_score = max(0.0, min(1.0, ratio))
risk_level = "low" if risk_score < 0.33 else "medium" if risk_score < 0.66 else "high"
```
Determinista, sin estado, sin dependencias externas. `model_version` fijo en `"mock-0.1"` para que el campo exista desde el día uno.

### 4. `request_id` como UUID4 generado en servidor
Garantiza unicidad sin coordinación. Cliente puede correlacionar logs. Más adelante se podrá aceptar un `Idempotency-Key` en header.

**Alternativa descartada:** autoincremental → requiere DB; no hay DB todavía.

### 5. `GET /predictions/{id}` como stub 501
No hay storage. Devolver 501 deja explícito que es contrato futuro y los tests pueden afirmarlo. Cuando entre persistencia, se cambia el status code y el body sin romper el path.

### 6. Tests con `httpx.AsyncClient` + `ASGITransport`
Permite testear la app sin levantar uvicorn. `pytest-asyncio` o `anyio` como runner; preferimos `anyio` (lo que usa FastAPI internamente) configurado vía `pytest.ini` o marker.

### 7. Dockerfile base `python:3.11-slim`
- Multi-step no necesario aún (sin compilación nativa).
- `pip install --no-cache-dir -r requirements.txt`.
- `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`.

### 8. Pinning de dependencias
`requirements.txt` con versiones pinneadas mínimas (`fastapi>=0.110,<0.120`, etc.) — evita romper builds reproducibles sin congelar a una versión exacta tan temprano. Se puede endurecer a hash-pinning más adelante.

## Risks / Trade-offs

- **División en error** (`income > 0` garantizado por `Field(gt=0)`) → mitigado por validación Pydantic; servicio asume input ya validado.
- **Algoritmo mock no es predictivo** → es explícito; `model_version` lo señala (`mock-0.1`). Riesgo de que alguien lo confunda con un modelo real → README lo dice en grande.
- **Stub 501 puede romper clientes** futuros si esperan 200 → aceptable en v0.1; documentado en el spec.
- **Pydantic v2 breaking vs v1**: si en el futuro alguna dependencia exige v1, hay fricción → asumido; v2 es la dirección.
- **Sin logging estructurado** desde S1 → trade-off consciente para no sobre-diseñar; se añade en semanas posteriores.

## Migration Plan

No aplica (greenfield). Para futuros consumidores: la sustitución de mock → modelo real conservará el shape de `RiskScoreResponse`; sólo cambiará `model_version` y la distribución de `risk_score`.

## Open Questions

- ¿Qué política de CORS aplicar? — por ahora ninguna (servicio interno). Decidir al exponer al frontend.
- ¿Versionado de path (`/v1/...`) ya en S1 o esperar? — propuesto **no** versionar todavía; añadir prefijo `/v1` cuando exista un primer cliente.
