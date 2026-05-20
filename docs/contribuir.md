# Cómo trabajar este repo

Guía operativa: cómo me organizo semana a semana. Pensada para mi yo del futuro, no para colaboradores externos.

---

## Convenciones de Git

### Branches

- `main` — siempre verde. Solo merges desde ramas de semana.
- `semana-N` — rama de trabajo de la semana en curso.
- `feature/<descripcion>` — opcional para sub-features grandes dentro de una semana.

### Commits

Conventional commits, español o inglés (consistencia dentro del commit):

```
chore: initialize FastAPI project structure
feat(api): add POST /risk-score endpoint
feat(model): train logistic regression model
fix(db): handle null in input_payload
refactor(service): extract ModelService
docs(architecture): update diagram with worker
test(batch): add idempotency tests
```

Tipos: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`, `style`.

### Tags

Al cerrar cada semana:

```powershell
git tag -a v0.1 -m "S1: FastAPI + endpoints mock"
git push origin v0.1
```

---

## Ciclo de una semana

1. **Lunes** — leer `docs/semana-N.md`. Crear rama `git checkout -b semana-N`.
2. **Lunes-miércoles** — estudiar conceptos. Apuntes en `docs/glosario.md` si aparece algo nuevo.
3. **Miércoles-viernes** — implementar. Commits pequeños y frecuentes.
4. **Sábado** — tests + documentación + ADR si hubo decisiones.
5. **Domingo** — merge a `main` + tag. Actualizar `README.md` (estado de la semana).

Si no llego: corro la semana, no acelero. Mejor cerrar bien que cerrar todo.

---

## Definition of Done por semana

- [ ] Código implementado y corriendo localmente.
- [ ] Tests pasan (`pytest`).
- [ ] README de la semana actualizado si hace falta.
- [ ] ADR(s) escritas en `docs/decisions.md` para decisiones reales.
- [ ] Roadmap actualizado: marcar checklist items completados.
- [ ] Diagrama de arquitectura refleja el estado actual.
- [ ] Merge a `main` + tag.

---

## Qué documento toco cuándo

| Cambio | Doc(s) a actualizar |
|--------|---------------------|
| Decisión técnica (A vs B) | `decisions.md` |
| Nuevo endpoint | `architecture.md` (contratos) + tests |
| Nueva dependencia | `requirements.txt` + `setup.md` si necesita instalación especial |
| Cambio de esquema DB | `architecture.md` (modelo de datos) + migración Alembic |
| Concepto que aprendí | `glosario.md` |
| Cierre de semana | `README.md` (tabla de estado) + `roadmap.md` (checklist) |
| Pregunta nueva de entrevista | `entrevista.md` |

---

## Anti-patrones a evitar

- **Estudiar sin construir.** El código siempre va primero, los conceptos se afianzan al implementar.
- **Sobre-arquitectura temprana.** En S1 no hay worker. No anticipar S5 en S1.
- **Tests al final.** Cada PR/commit que agrega lógica tiene su test.
- **Saltarse semanas.** El proyecto crece por capas. Saltar S3 rompe S4.
- **No documentar decisiones.** Sin ADR, las elecciones se olvidan y no se pueden defender en entrevista.
- **Perfeccionismo en código.** Esto es un proyecto de portfolio + aprendizaje. Funcional > elegante.
