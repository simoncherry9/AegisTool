# AegisWiFi — Durable, non-obvious code conventions

## Code style
- Python 3.13+, strict typing (mypy strict), `from __future__ import annotations` in EVERY module
- Ruff linting: E/F/I/UP/B/SIM/ASYNC/S/PL, line-length 100, double quotes
- Domain model in `aegiswifi.database.models`; DTOs (Pydantic) in `*/schemas.py`; business logic in `*/service.py`
- NEVER return ORM models from API — always convert to DTOs (Pydantic `from_attributes=True`)
- States as `enum.StrEnum` — stored as String columns in SQLite
- Import pattern: always `from aegiswifi.x import y` (package dir is `backend/aegiswifi/`)

## Architecture rules
- **Scope Engine first:** PolicyEngine.assert_allowed() guards every active action (§12.4)
- **No shell=True:** Always `subprocess.run(..., shell=False)` or `asyncio.create_subprocess_exec` with arg lists, only approved binaries
- **API bound to 127.0.0.1 by default** (§34)
- **Secrets encrypted** via `aegiswifi.core.security` (Fernet); redacted in logs/reports (§19)
- **Evidence immutable:** SHA-256 + tool + version on every capture; no overwrites (§30)
- **Interface restore:** All monitor-mode prep must be reversible; engagement close stops jobs + restores interfaces (§11/§13)
- **Web backend NOT run as root** (§34)

## Module structure pattern
- Module dir: `aegiswifi/<module>/` with `__init__.py`, `schemas.py` (Pydantic DTOs), `service.py` (business logic)
- Adapters (future): inherit from `aegiswifi.adapters.base.ToolAdapter` (§27); core NEVER parses tool text directly
- Sync DB chosen intentionally: Wi-Fi tools are subprocess, not async; job queue handles its own workers

## Git conventions
- Messages in imperative with module prefix: `engagements: validate permissions before creating job`
- Never commit: data/, *.pcap, *.22000, .env, secrets