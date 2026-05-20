# Semana 1 — Fundamentos + FastAPI

**Objetivo:** entender el rol y dejar una API FastAPI corriendo con endpoints mock.

**Tag al cerrar:** `v0.1`

---

## Qué estudiar

- Diferencia training vs inference.
- Batch vs online prediction.
- Qué es model serving.
- Python intermedio: tipos, dataclasses, async básico, packaging.
- FastAPI: routing, dependencias, Pydantic, OpenAPI auto.
- Pytest básico + `httpx.AsyncClient` para test de endpoints.

Recursos sugeridos:
- FastAPI docs oficiales (tutorial completo).
- Real Python: "Python Type Checking" + "Async IO".
- Pydantic v2 migration guide.

---

## Qué construir

API mínima con:

```
GET  /health           → { "status": "ok" }
POST /risk-score       → predicción mockeada (hardcoded)
GET  /predictions/{id} → not implemented yet (501) o mock
```

### Schemas (Pydantic)

```python
class RiskScoreRequest(BaseModel):
    income: float = Field(gt=0)
    age: int = Field(ge=18, le=100)
    debt: float = Field(ge=0)
    employment_years: int = Field(ge=0)

class RiskScoreResponse(BaseModel):
    request_id: UUID
    risk_score: float
    risk_level: Literal["low", "medium", "high"]
    model_version: str
```

### Lógica mock

`risk_score = (debt / income)` clipeado a [0, 1], y bucketed en low/medium/high. Sin modelo real todavía.

---

## Estructura objetivo al fin de semana

```
ai-risk-scoring-platform/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app + routers
│   ├── config.py                # Settings (pydantic-settings)
│   ├── api/
│   │   └── routes/
│   │       ├── health.py
│   │       └── predictions.py
│   ├── schemas/
│   │   └── prediction.py
│   └── services/
│       └── prediction_service.py  # mock
├── tests/
│   ├── conftest.py
│   └── test_predictions.py
├── requirements.txt
├── Dockerfile
├── .env.example
├── .gitignore
└── README.md
```

---

## Tareas

- [ ] Crear `requirements.txt` con FastAPI + uvicorn + pydantic + pytest + httpx.
- [ ] Crear estructura de carpetas de arriba.
- [ ] Implementar `GET /health`.
- [ ] Implementar `POST /risk-score` con lógica mockeada.
- [ ] Validación con Pydantic (campos, rangos, tipos).
- [ ] Tests: happy path + 422 por input inválido + health.
- [ ] Dockerfile + verificar build local.
- [ ] README con instrucciones de correr y testear.
- [ ] Commit inicial: `chore: initialize FastAPI project structure`.
- [ ] Tag `v0.1`.

---

## Criterios de cierre

- `uvicorn app.main:app --reload` levanta sin errores.
- http://localhost:8000/docs muestra los endpoints con schemas correctos.
- `pytest` pasa con al menos 5 tests.
- `docker build -t risk-api .` funciona.
- README explica setup + run + test.

---

## Preguntas que tengo que poder responder al cerrar S1

- ¿Qué diferencia hay entre training e inference?
- ¿Cuándo usaría batch vs online prediction?
- ¿Qué hace FastAPI con un Pydantic model en el body?
- ¿Cómo valido que `age` esté entre 18 y 100?
- ¿Por qué uso `UUID` para `request_id` y no un autoincremental?
