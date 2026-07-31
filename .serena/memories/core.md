# AegisWiFi — Top-level source map and project-wide invariants

## What it is
Professional wireless network auditing platform for Kali Linux. Pre-alpha. Backend in `backend/aegiswifi/` (Python package `aegiswifi`), frontend skeleton in `frontend/`. Specification: `minuta.md` (fuente de verdad del alcance).

## Current state (Phase 0 + partial 1 + 2)
- Core: FastAPI app factory, config (pydantic-settings), structlog logging, Fernet crypto, domain exceptions
- Database: SQLAlchemy 2 + SQLite, all 8 models + TimestampMixin (see `mem:tech_stack`)
- Engagements: CRUD, activate/close, expiry checks
- Scope: YAML parser → PolicyEngine with §12.4 validations (10 pre-flight checks per action)
- API: `/health`, `/api/v1/engagements` CRUD
- CLI: `aegiswifi` (version, serve, engagement create/activate, scope import)
- Tests: health, scope (parser + policy), security — conftest uses in-memory SQLite
- Migration: Alembic initial (0001)
- Frontend: Only `index.html` + `vite.config.ts` — no React code yet

## Key rules (from `mem:conventions` and AGENTS.md)
- Scope Engine FIRST: no active action runs without PolicyEngine.assert_allowed
- No shell=True: always `asyncio.create_subprocess_exec` with arg lists
- API bound to 127.0.0.1 by default (§34)
- Secrets encrypted at rest via Fernet (`mem:core/security`)
- Evidence immutable: SHA-256, tool, version, chain of custody
- Interface restore on engagement close
- Web backend NOT run as root

## Key gaps (what the codebase says doesn't exist yet)
From `mem:core/gaps` for full details, but at high level: no WebSocket, no JobManager/Queue, no hardware module, no adapters, no discovery, no handshake/PMKID capture, no cracking, no findings engine, no reporting, no real frontend, no docs beyond README/AGENTS/minuta.

## References
- Engagements and scope: `mem:core/domain`
- Gaps and roadmap: `mem:core/gaps`
- Security internals: `mem:core/security`
- Tech stack: `mem:tech_stack`
- Tests: `mem:core/tests`
- CLI: `mem:core/cli`
- Frontend state: `mem:frontend/core`
- Configuration: `mem:core/config`
- Development conventions: `mem:conventions`