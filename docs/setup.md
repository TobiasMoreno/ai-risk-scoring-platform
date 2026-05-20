# Setup del entorno local (Windows)

Guía para dejar la máquina lista para trabajar el proyecto. PowerShell por defecto.

---

## 1. Prerequisitos

| Herramienta | Versión mínima | Para qué |
|-------------|----------------|----------|
| Python | 3.11+ | App principal |
| Git | 2.40+ | Control de versiones |
| Docker Desktop | última estable | PostgreSQL, RabbitMQ, Prometheus, Grafana |
| VS Code (o IDE) | — | Editor (extensiones: Python, Pylance, Docker) |
| Make (opcional) | — | Atajos de comandos. Alternativa: scripts `.ps1` |

### Verificar instalación

```powershell
python --version    # 3.11+
git --version
docker --version
docker compose version
```

---

## 2. Clonar y entrar al repo

```powershell
cd "C:\Users\Tobias\Desktop\Programación\PAGINAS WEB\ai-risk-scoring-platform"
```

---

## 3. Entorno virtual de Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea el script de activación:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Para desactivar: `deactivate`.

---

## 4. Dependencias

A partir de S1 va a existir `requirements.txt` (o `pyproject.toml`):

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

Dependencias mínimas de arranque (S1):
- `fastapi`
- `uvicorn[standard]`
- `pydantic`
- `pydantic-settings`
- `pytest`
- `httpx` (para tests del cliente)

A partir de S2: `scikit-learn`, `joblib`, `numpy`, `pandas`.
A partir de S3: `sqlalchemy`, `psycopg[binary]`, `alembic`.
A partir de S5: `pika` (RabbitMQ) o `aiokafka`.
A partir de S6: `prometheus-client`, `structlog`, `opentelemetry-*`.

---

## 5. Variables de entorno

```powershell
Copy-Item .env.example .env
```

Editar `.env` según corresponda (DB password, etc.).

---

## 6. Correr la API

```powershell
uvicorn app.main:app --reload --port 8000
```

- Health: http://localhost:8000/health
- OpenAPI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 7. Docker Compose (S3+)

```powershell
docker compose up -d         # levantar
docker compose ps            # estado
docker compose logs -f api   # logs
docker compose down          # bajar
docker compose down -v       # bajar + borrar volúmenes
```

Servicios esperados: `api`, `postgres`, `rabbitmq`, `prometheus`, `grafana`.

---

## 8. Tests

```powershell
pytest                       # todos
pytest -v                    # verbose
pytest tests/unit            # unitarios
pytest -k risk_score         # filtrar por nombre
pytest --cov=app             # con cobertura
```

---

## 9. Linters / formateo (recomendado)

```powershell
pip install ruff black mypy
ruff check .
black .
mypy app
```

---

## 10. Problemas comunes

| Síntoma | Causa | Solución |
|---------|-------|----------|
| `Activate.ps1 cannot be loaded` | Execution policy | `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| `psycopg` falla al instalar | Falta build tools | Usar `psycopg[binary]` |
| Docker `port already in use` | Servicio local ocupando puerto | Cambiar puerto en `docker-compose.yml` o `.env` |
| `uvicorn` no encuentra `app.main` | `cwd` incorrecto | Correr desde la raíz del repo |
| Modelo no carga | `MODEL_PATH` mal en `.env` | Verificar ruta relativa a la raíz |
