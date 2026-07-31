# AegisWiFi — Complete gap analysis against minuta.md specification

## Fully implemented
- Setup (F0): repo, README, license, linter, pyproject.toml, Makefile, install.sh, uninstall.sh
- Core (F1): FastAPI factory, config (pydantic-settings), structlog logging, domain exceptions, Fernet crypto
- Database (F1): All 8 SQLAlchemy models + TimestampMixin, engine with singleton pattern, Alembic initial migration
- Engagements (F2): CRUD, code generation (ENG-YYYY-NNN), activate/close/expiry
- Scope (F2): YAML parser, Pydantic schemas, PolicyEngine with all §12.4 pre-flight checks
- API (F1+F2): /health, /api/v1/engagements (list/create/get/update/activate/close)
- CLI (F2): version, serve, engagement create/activate, scope import
- Tests: health, scope (parser + policy), security — conftest with in-memory SQLite

## Partially implemented (structure exists, needs completion)
- Frontend: Only index.html + vite.config.ts exist — no React app, no pages/components/stores/api layer

## Not implemented at all (gap)
- **WebSocket:** No WebSocket support, no event streaming, no job progress streaming (§8, §26, §32)
- **Job system (§26):** No JobManager, JobQueue, ProcessSupervisor — no persistence for background work
- **Hardware module (§13 + F3):** No interface detection, monitor mode, chipset/driver query, injection test, restore
- **Adapters (§27):** No ToolAdapter base class, no adapters (Kismet, Airodump, Hcxdumptool, Hashcat, Tshark, etc.)
- **Discovery module (§14 + F4):** No AP/station inventory, no channel hopping, no RSN parser, no WPS/PMF/WPA3 detection
- **Handshake module (§15 + F5):** No EAPOL capture/parse/validate, no quality assessment
- **PMKID module (§16 + F5):** No PMKID detection/validate/conversion
- **Conversion module (§17 + F5):** No 22000 format conversion
- **Cracking module (§18 + F6):** No Hashcat adapter, benchmark, dictionary/rule/mask management, keyspace, restore, temperature, result protection
- **Findings engine (§29 + F7):** No rule engine, no finding generation from evidence
- **Reporting (§31 + F7):** No HTML/PDF/JSON export, no Jinja2 templates
- **Evidence store (§30):** No programmatic directory structure, chain of custody, SHA-256 auto-hashing
- **WPS module (§21 + F8):** No Reaver/Bully adapters, no WPS enumeration
- **PMF module (§22 + F8):** No PMF validation tests
- **Enterprise module (§23 + F9):** No EAP parser, certificate analysis, EAPHammer adapter
- **Isolation tests (§24):** Not started
- **Rogue AP detection (§25):** Not started
- **Rules directory:** No YAML rules for finding engine (rules/ directory doesn't exist)
- **Report templates:** No Jinja2 templates for reports (report_templates/ directory doesn't exist)
- **Docs:** architecture.md, data-model.md, threat-model.md, conventions.md, roadmap.md all missing (only AGENTS.md + README exist)

## Missing test infrastructure
- No engagement API tests (only health + scope + security)
- No integration tests
- No PCAP fixtures for handshake testing (§36)
- No lab setup (mac80211_hwsim, hostapd, FreeRADIUS)