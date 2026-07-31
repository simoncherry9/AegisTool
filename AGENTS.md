# AGENTS.md — Guía para agentes de desarrollo en AegisWiFi

> Lee este archivo **antes** de modificar el repositorio. Describe cómo está
> organizado el proyecto, qué reglas son innegociables y dónde encontrar cada cosa.

## Qué es AegisWiFi

Plataforma profesional de auditoría inalámbrica para Kali Linux. El producto se
describe por completo en `minuta.md` (fuente de verdad del alcance); este archivo
describe **cómo** trabajarlo.

## Fuentes de verdad

1. `minuta.md` — especificación funcional completa (una sección por módulo).
2. `docs/architecture.md` — capas, componentes y flujo de jobs.
3. `docs/data-model.md` — entidades y relaciones (sección 28 de la minuta).
4. `docs/threat-model.md` — modelo de amenazas.
5. `docs/conventions.md` — estilo, tests, commits, seguridad.

Cuando una decisión toque **seguridad o alcance**, cita la sección de `minuta.md`
que la respalda (p. ej. *(minuta §12.4)*).

## Reglas innegociables

Estas reglas no son negotiables; si una tarea las contradice, detente y pregunta.

- **Scope Engine primero.** Ninguna acción activa (captura dirigida, reconexión,
  cracking, WPS, rogue AP, deauth, fuzzing) puede ejecutarse sin validarse contra
  el alcance del *engagement* activo. El chequeo vive en
  `aegiswifi.scope.policy.PolicyEngine`, **no** en el handler de la API.
- **No shell.** Invoca herramientas externas con listas de argumentos
  (`asyncio.create_subprocess_exec` / `subprocess.run(..., shell=False)`), nunca
  con `shell=True` ni strings concatenados. Solo binarios de una lista permitida.
- **API solo en localhost.** La API escucha en `127.0.0.1` por defecto. No la
  expongas fuera de localhost sin revisión explícita (minuta §34).
- **Secretos protegidos.** Las contraseñas recuperadas se cifran en BD
  (`aegiswifi.core.security`), se redactan en logs/informes/notificaciones. Nunca
  loguear un secreto en texto plano (minuta §19).
- **Evidencia inmutable.** No sobrescribir archivos de evidencia; registrar siempre
  SHA-256, herramienta, versión y cadena de custodia (minuta §30).
- **Restauración.** Toda preparación de interfaz (monitor mode, etc.) debe poder
  revertirse. El cierre de un *engagement* detiene trabajos y restaura interfaces
  (minuta §11/§13).
- **No root para la UI.** Las operaciones privilegiadas van por un helper mínimo;
  el backend web **no** corre como root (minuta §34).

## Estructura del backend — paquete `aegiswifi`

Importa siempre como `from aegiswifi.x import y`. El directorio del paquete es
`backend/aegiswifi/` (mapeado a `aegiswifi` vía `pyproject.toml`).

```
backend/aegiswifi/
├── main.py        # create_app() — fábrica de la API FastAPI
├── cli.py         # CLI Typer (comando `aegiswifi`)
├── core/          # config, logging, security, exceptions
├── api/v1/        # routers REST (/health, /engagements, …)
├── database/      # engine, base declarativa, modelos SQLAlchemy (§28)
├── engagements/   # modelo + servicio + DTO de engagements
├── scope/         # PolicyEngine, parser YAML de alcance
└── …              # jobs, adapters, discovery, handshake, cracking, findings,
                  # reporting — esqueletos en fases posteriores (ver roadmap.md)
```

## Cómo ejecutar

```bash
pip install -e ".[dev]"
make migrate          # crea el esquema en SQLite
make dev              # uvicorn con reload sobre 127.0.0.1:8000
make test             # pytest
make lint             # ruff + mypy
```

## Convenciones de código

- Python 3.13 (mín. 3.12), tipado estricto (mypy strict),
  `from __future__ import annotations` en todo módulo.
- Ruff: `E/F/I/UP/B/SIM/ASYNC/S/PL`, line-length 100, comillas dobles.
- **Modelo de dominio** en `aegiswifi.database.models`; **DTOs** Pydantic en
  `*/schemas.py`; **lógica** en `*/service.py`. No devuelvas modelos ORM en la
  API: conviértelos a DTOs.
- **Estados** como `enum.Enum` (`EngagementStatus`, `JobStatus`, …). Ver secciones
  11/18/26 de la minuta.
- **Adaptadores** heredan de `aegiswifi.adapters.base.ToolAdapter` (§27) y
  normalizan la salida textual. El core **nunca** parsea texto de herramienta
  directamente.

## Tests

- `backend/tests/` con pytest + httpx (TestClient/ASGITransport).
- Toda función con branches (parsers, validadores, PolicyEngine, adaptadores)
  necesita unit tests. Cobertura es un criterio de cierre (§39).
- Compromiso de la Fase 1: la app inicia, persiste jobs y transmite eventos.

## Commits

- Mensajes en imperativo, prefijo de módulo:
  `engagements: valida permisos antes de crear job`.
- **Nunca** commitear `data/`, `*.pcap`, `*.22000`, `.env`, ni ningún secreto.

## Qué todavía NO existe (no asumir implementado)

Sistema de jobs persistente, WebSocket, adaptadores, parsers, frontend real,
reportes. Consulta `docs/roadmap.md` para la fase actual antes de asumir que algo
existe.
