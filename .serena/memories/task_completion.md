# AegisWiFi — Task completion commands

Run these in order when finishing a coding task:

1. Format & lint fix: `make fmt` (runs `ruff format backend` + `ruff check --fix backend`)
2. Type check: `make typecheck` (runs `mypy backend/aegiswifi`)
3. Tests: `make test` (runs `pytest -q -ra`)
4. Full lint: `make lint` (runs `ruff check backend` + `mypy backend/aegiswifi`)

All commands from repo root. Ensure `.venv` is activated or `pip install -e ".[dev]"` has been run.

## Install dependencies
- Backend: `pip install -e ".[dev]"` (from repo root)
- Frontend: `cd frontend && npm install`

## Run the application
- API dev: `make dev` (uvicorn with reload on 127.0.0.1:8000)
- CLI: `python -m aegiswifi.cli --help`
- Migrate: `make migrate` (alembic upgrade head)

## Notes
- Tests run against SQLite in-memory (conftest handles this)
- Windows users: `make` not available natively; use `pip` and `python -m` directly
- API is bound to localhost only (§34)