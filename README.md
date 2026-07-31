# AegisWiFi

**Plataforma profesional de auditoría de redes inalámbricas** · Kali Linux · Python + FastAPI · React + TypeScript · SQLite

> Plataforma profesional de evaluación inalámbrica para detectar configuraciones inalámbricas inseguras, validar la fortaleza de credenciales, comprobar segmentación, identificar puntos de acceso fraudulentos y generar evidencia técnica reproducible.

---

## ⚠️ Uso autorizado

AegisWiFi está pensado **exclusivamente** para redes propias, laboratorios y auditorías expresamente autorizadas. El motor de políticas bloquea toda acción fuera del alcance definido: ninguna funcionalidad activa se ejecuta sin un *engagement* válido y autorización de objetivo. El uso sobre redes de terceros sin consentimiento explícito es ilegal y queda **fuera** del propósito del proyecto. Ver `docs/threat-model.md` y las secciones 5 y 12 de `minuta.md`.

---

## Estado

**Pre-Alpha — Fase 0/1** (preparación del repositorio y núcleo del backend). Consulta `docs/roadmap.md`.

---

## Stack

- **Backend:** Python 3.13 (mín. 3.12) · FastAPI · Uvicorn · Pydantic · SQLAlchemy 2 · Alembic · SQLite · Typer · asyncio · structlog · Cryptography
- **Frontend:** React · TypeScript · Vite · Tailwind · TanStack Query · Zustand · React Router · Recharts · Zod
- **Herramientas integradas (Kali):** iw · iproute2 · rfkill · aircrack-ng · hcxdumptool · hcxtools · Hashcat · Kismet · tshark · Reaver · Bully · Pixiewps · EAPHammer · hostapd(-wpe) · Nmap

---

## Estructura

```
aegiswifi/                      # raíz del repositorio (aquí, ./)
├── backend/aegiswifi/          # API + motor de auditoría (paquete importable `aegiswifi`)
│   ├── core/                   # config, logging, security, exceptions
│   ├── api/v1/                 # routers REST
│   ├── database/              # engine + base + modelos SQLAlchemy (sección 28)
│   ├── engagements/  scope/   # módulos de dominio
│   └── …                      # jobs, adapters, discovery, findings, reporting (fases siguientes)
├── frontend/                  # panel web (Vite + React + TS)
├── rules/                     # reglas de hallazgos en YAML (wireless, cracking, password, reporting)
├── report_templates/          # plantillas Jinja2
├── wordlists/                 # diccionarios
├── scripts/  migrations/      # helpers y migraciones Alembic
├── docs/                      # arquitectura, modelo de datos, amenazas, convenciones, roadmap
└── lab/                       # laboratorio mac80211_hwsim / hostapd / FreeRADIUS
```

Detalle de capas y módulos en `docs/architecture.md`.

---

## Inicio rápido (Kali Linux)

```bash
git clone <repo> && cd aegiswifi
cp config.example.yaml config.yaml           # opcional: ajustar valores
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make migrate                                   # alembic upgrade head  (crea el esquema en SQLite)
aegiswifi --help                               # CLI
aegiswifi serve                                # API en 127.0.0.1:8000
# Frontend, en otra terminal:
cd frontend && npm install && npm run dev
```

> **Windows/Linux sin adaptador:** el backend y el frontend arrancan sin hardware Wi-Fi. Las funciones que tocan `iw`/`ip`/`aircrack-ng`/`Hashcat` solo operan sobre Kali con periféricos compatibles.

---

## Documentación

| Documento | Contenido |
| --- | --- |
| `minuta.md` | Especificación funcional completa (fuente de verdad del alcance) |
| `AGENTS.md` | Guía para agentes de desarrollo que trabajen en el repo |
| `docs/architecture.md` | Capas, componentes y flujo de jobs |
| `docs/data-model.md` | Entidades y relaciones (sección 28 de la minuta) |
| `docs/threat-model.md` | Modelo de amenazas inicial |
| `docs/conventions.md` | Estilo, tests, commits, reglas de seguridad |
| `docs/roadmap.md` | Fases y estado |

---

## Licencia

GPL-3.0-only. Ver `LICENSE`.
