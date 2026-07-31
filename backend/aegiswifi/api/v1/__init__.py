"""Versión 1 de la API REST. Router agregado en ``__init__.api_router``."""

from __future__ import annotations

from fastapi import APIRouter

from aegiswifi.api.v1 import auth, engagements, health, jobs, users
from aegiswifi.discovery import api as discovery_api
from aegiswifi.evidence import api as evidence_api
from aegiswifi.cracking import api as cracking_api
from aegiswifi.interfaces import api as interfaces_api
from aegiswifi.validation import api as validation_api
from aegiswifi.findings import api as findings_api
from aegiswifi.tools import api as tools_api

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(health.router)
api_router.include_router(engagements.router)
api_router.include_router(jobs.router)
api_router.include_router(jobs.ws_router)
api_router.include_router(evidence_api.router)
api_router.include_router(interfaces_api.router)
api_router.include_router(cracking_api.router)
api_router.include_router(validation_api.router)
api_router.include_router(findings_api.router)
api_router.include_router(discovery_api.router)
api_router.include_router(discovery_api.ws_router)
api_router.include_router(tools_api.router)

__all__ = ["api_router"]
