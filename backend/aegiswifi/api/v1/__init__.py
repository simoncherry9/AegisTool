"""Versión 1 de la API REST. Router agregado en ``__init__.api_router``."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from aegiswifi.api.v1 import auth, engagements, health, jobs, users
from aegiswifi.cracking import api as cracking_api
from aegiswifi.deauth import api as deauth_api
from aegiswifi.discovery import api as discovery_api
from aegiswifi.evidence import api as evidence_api
from aegiswifi.findings import api as findings_api
from aegiswifi.handshake import api as handshake_api
from aegiswifi.interfaces import api as interfaces_api
from aegiswifi.pmkid import api as pmkid_api
from aegiswifi.reporting import api as reporting_api
from aegiswifi.tools import api as tools_api
from aegiswifi.validation import api as validation_api
from aegiswifi.wps import api as wps_api

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(health.router)
protected = [Depends(auth.require_api_user)]
api_router.include_router(users.router, dependencies=protected)
api_router.include_router(engagements.router, dependencies=protected)
api_router.include_router(jobs.router, dependencies=protected)
api_router.include_router(jobs.ws_router)
api_router.include_router(evidence_api.router, dependencies=protected)
api_router.include_router(interfaces_api.router, dependencies=protected)
api_router.include_router(cracking_api.router, dependencies=protected)
api_router.include_router(validation_api.router, dependencies=protected)
api_router.include_router(findings_api.router, dependencies=protected)
api_router.include_router(discovery_api.router, dependencies=protected)
api_router.include_router(discovery_api.ws_router)
api_router.include_router(tools_api.router, dependencies=protected)
api_router.include_router(handshake_api.router, dependencies=protected)
api_router.include_router(pmkid_api.router, dependencies=protected)
api_router.include_router(deauth_api.router, dependencies=protected)
api_router.include_router(wps_api.router, dependencies=protected)
api_router.include_router(reporting_api.router, dependencies=protected)

__all__ = ["api_router"]
