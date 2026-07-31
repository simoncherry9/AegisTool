# AegisWiFi — Language, frameworks, build tools, and package management

## Backend
- **Language:** Python 3.13 (min 3.12), strict typing (mypy strict), `from __future__ import annotations` everywhere
- **Web framework:** FastAPI 0.115+ / Uvicorn 0.32+
- **Validation:** Pydantic 2.9+ / pydantic-settings 2.6+
- **Database:** SQLAlchemy 2.0+ / SQLite (default) with Alembic 1.13+ for migrations
- **CLI:** Typer 0.13+
- **Security:** Cryptography 43+ (Fernet symmetric encryption)
- **Logging:** Structlog 24.4+
- **Templating:** Jinja2 3.1+
- **System:** Psutil 6.1+ (CPU, GPU, disk monitoring)
- **Future/optional:** PostgreSQL via psycopg (psycopg[binary] extra)

## Frontend
- **Language:** TypeScript (React)
- **Build:** Vite
- **Stack (planned):** Tailwind CSS, TanStack Query, Zustand, React Router, Recharts, Zod
- **Current state:** Only `index.html` + `vite.config.ts` exist — no React code yet

## Tooling
- **Linter:** Ruff (select: E/F/I/UP/B/SIM/ASYNC/S/PL), line-length 100, double quotes
- **Type checker:** Mypy (strict mode, pydantic plugin)
- **Test runner:** Pytest 8.3+ with pytest-asyncio, httpx (TestClient/ASGITransport), asyncio_mode=auto
- **CI:** Not configured yet

## Packaging
- **Build:** setuptools + wheel, `backend/aegiswifi/` → importable package `aegiswifi`
- **Entry point:** `aegiswifi.cli:app` (Typer app)
- **Dev install:** `pip install -e ".[dev]"`