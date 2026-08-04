# AegisWiFi

**Plataforma profesional de auditoría de redes inalámbricas** · Kali Linux · Python + FastAPI · React + TypeScript · SQLite

> Plataforma profesional de evaluación inalámbrica para detectar configuraciones inalámbricas inseguras, validar la fortaleza de credenciales, comprobar segmentación, identificar puntos de acceso fraudulentos y generar evidencia técnica reproducible.

---

## ⚠️ Uso autorizado

AegisWiFi está pensado **exclusivamente** para redes propias, laboratorios y auditorías expresamente autorizadas. El motor de políticas bloquea toda acción fuera del alcance definido: ninguna funcionalidad activa se ejecuta sin un *engagement* válido y autorización de objetivo. El uso sobre redes de terceros sin consentimiento explícito es ilegal y queda **fuera** del propósito del proyecto. Ver las secciones 5 y 12 de `minuta.md`.

---

## Estado

**Pre-Alpha funcional.** Incluye API, autenticación, engagements, alcance, trabajos, evidencia, discovery, validación, cracking, hallazgos, informes y panel web. Las operaciones inalámbricas requieren Kali Linux y hardware compatible.

---

## Stack

- **Backend:** Python 3.13 (mín. 3.12) · FastAPI · Uvicorn · Pydantic · SQLAlchemy 2 · Alembic · SQLite · Typer · asyncio · structlog · Cryptography
- **Frontend:** React · TypeScript · Vite · React Router · CSS propio
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
│   └── …                      # jobs, adapters, discovery, findings, reporting
├── frontend/                  # panel web (Vite + React + TS)
├── migrations/                # migraciones Alembic
├── data/                      # datos runtime (no se versionan)
└── minuta.md                  # especificación funcional y de seguridad
```

---

## Inicio rápido (Kali Linux)

```bash
git clone <repo> && cd aegiswifi
cp config.example.yaml config.yaml           # opcional: ajustar valores
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make migrate                                   # alembic upgrade head  (crea el esquema en SQLite)
aegiswifi --help                               # CLI
aegiswifi serve                                # API en 127.0.0.1:8001
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

---

## Licencia

GPL-3.0-only. Ver `LICENSE`.
