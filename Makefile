# AegisWiFi — tareas comunes. Uso: make <target>
# Pensado para Kali Linux; some targets requieren Python/Node instalados.

PYTHON ?= python
PIP    ?= pip
ALEMBIC = $(PYTHON) -m alembic -c backend/alembic.ini

.PHONY: help install dev serve migrate makemigrations rollback test lint fmt typecheck frontend frontend-dev frontend-build clean

help: ## Mostrar targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS":.*## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Instalar backend (editable) + frontend
	$(PIP) install -e ".[dev]"
	cd frontend && npm install

dev: ## Levantar API con recarga (127.0.0.1:8000)
	$(PYTHON) -m uvicorn aegiswifi.main:app --reload --host 127.0.0.1 --port 8000

serve: ## Levantar API en modo producción
	$(PYTHON) -m uvicorn aegiswifi.main:app --host 127.0.0.1 --port 8000

migrate: ## Aplicar migraciones (alembic upgrade head)
	$(ALEMBIC) upgrade head

makemigrations: ## Crear migración autogenerada. Uso: make makemigrations m="mensaje"
	$(ALEMBIC) revision --autogenerate -m "$(m)"

rollback: ## Revertir una migración
	$(ALEMBIC) downgrade -1

test: ## Ejecutar tests
	$(PYTHON) -m pytest

lint: ## Ruff (check) + mypy
	$(PYTHON) -m ruff check backend
	$(PYTHON) -m mypy backend/aegiswifi

fmt: ## Formatear y arreglar
	$(PYTHON) -m ruff format backend
	$(PYTHON) -m ruff check --fix backend

typecheck: ## Solo mypy
	$(PYTHON) -m mypy backend/aegiswifi

frontend: ## Instalar dependencias del frontend
	cd frontend && npm install

frontend-dev: ## Levantar Vite dev server
	cd frontend && npm run dev

frontend-build: ## Compilar frontend
	cd frontend && npm run build

clean: ## Limpiar artefactos
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
