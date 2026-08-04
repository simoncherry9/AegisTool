"""Policy Engine — autoriza o bloquea cada acción (minuta §12, §34).

El PolicyEngine es el **guardián** del sistema. Antes de cualquier acción activa,
cualquier módulo debe invocar ``PolicyEngine.assert_allowed`` con el contexto de
la acción. Las validaciones previas de §12.4 se aplican aquí.

Diseño:
  * No depende de la BD; opera sobre un :class:`ScopeContext` resuelto en runtime
    a partir del engagement + archivo de alcance importado.
  * El contador de tramas activas / tiempo de cracking se persiste por engagement
    y se inyecta vía :class:`Usage`. En esta fase es 0 (llevado por el JobManager).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from aegiswifi.core.exceptions import ScopeViolation
from aegiswifi.scope.schemas import Limits, Permissions, ScopeBlock


@dataclass
class Usage:
    """Contadores de uso actuales del engagement (lo lleva el JobManager)."""

    active_frames_sent: int = 0
    cracking_minutes_used: int = 0
    current_gpu_temp: int = 0


@dataclass
class ScopeContext:
    """Contexto de alcance resuelto para un engagement activo (minuta §12)."""

    engagement_code: str
    valid_from: datetime
    valid_until: datetime
    scope: ScopeBlock
    permissions: Permissions
    limits: Limits
    operator: str
    usage: Usage = field(default_factory=Usage)

    def is_temporally_valid(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        return self.valid_from <= now <= self.valid_until

    def is_target_in_scope(
        self, *, ssid: str | None = None, bssid: str | None = None, client: str | None = None
    ) -> bool:
        """¿El objetivo (SSID/BSSID/cliente) está dentro del alcance autorizado?"""
        allowed_any = not (
            self.scope.allowed_ssids or self.scope.allowed_bssids or self.scope.allowed_clients
        )
        if allowed_any:
            # Sin lista explícita → todo objetivo está permitido.
            return True
        if ssid and self.scope.allowed_ssids and ssid not in self.scope.allowed_ssids:
            return False
        if bssid and self.scope.allowed_bssids and bssid not in self.scope.allowed_bssids:
            return False
        return not (
            client and self.scope.allowed_clients and client not in self.scope.allowed_clients
        )


class PolicyEngine:
    """Aplica las validaciones previas de §12.4 antes de ejecutar una acción."""

    def __init__(self, context: ScopeContext) -> None:
        self.ctx = context

    def assert_allowed(
        self,
        action: str,
        *,
        ssid: str | None = None,
        bssid: str | None = None,
        client: str | None = None,
        channel: int | None = None,
        band: str | None = None,
    ) -> None:
        """Valida una acción activa; lanza :class:`ScopeViolation` si falla.

        Las 10 validaciones previas de §12.4 se cubren así:
          1-3 (engagement activo, fecha, operador) → resueltos al construir el ctx.
          4 (objetivo incluido) → :meth:`is_target_in_scope`.
          5 (acción permitida) → :meth:`_assert_permitted`.
          6-10 (interfaz, límite tramas, canal, kill switch, disco) → aquí/JobManager.
        """
        self._assert_temporal()
        self._assert_target(ssid=ssid, bssid=bssid, client=client)
        self._assert_permitted(action)
        if (
            channel is not None
            and self.ctx.scope.channels
            and channel not in self.ctx.scope.channels
        ):
            raise ScopeViolation(f"canal {channel} fuera del alcance")
        if band is not None and self.ctx.scope.bands and band not in self.ctx.scope.bands:
            raise ScopeViolation(f"banda {band} fuera del alcance")

    def _assert_temporal(self) -> None:
        if not self.ctx.is_temporally_valid():
            raise ScopeViolation(
                f"engagement {self.ctx.engagement_code} fuera de su ventana temporal"
            )

    def _assert_target(self, *, ssid: str | None, bssid: str | None, client: str | None) -> None:
        if not self.ctx.is_target_in_scope(ssid=ssid, bssid=bssid, client=client):
            raise ScopeViolation(
                f"objetivo fuera del alcance (ssid={ssid}, bssid={bssid}, client={client})"
            )

    _PERMISSION_FIELD: dict[str, str] = {
        "passive_capture": "passive_capture",
        "handshake_capture": "handshake_capture",
        "pmkid_capture": "pmkid_capture",
        "controlled_reconnect": "controlled_reconnect",
        "password_audit": "password_audit",
        "wps_testing": "wps_testing",
        "enterprise_testing": "enterprise_testing",
        "denial_of_service": "denial_of_service",
        "protocol_fuzzing": "protocol_fuzzing",
    }

    def _assert_permitted(self, action: str) -> None:
        field_name = self._PERMISSION_FIELD.get(action)
        if field_name is None:
            raise ScopeViolation(f"acción desconocida para el PolicyEngine: {action}")
        allowed = getattr(self.ctx.permissions, field_name)
        if not allowed:
            raise ScopeViolation(f"permiso '{action}' no concedido para este engagement")

    def assert_within_frame_budget(self) -> None:
        if self.ctx.usage.active_frames_sent >= self.ctx.limits.maximum_active_frames:
            raise ScopeViolation(
                f"límite de tramas activas alcanzado ({self.ctx.limits.maximum_active_frames})"
            )

    def assert_within_cracking_budget(self) -> None:
        if (
            self.ctx.usage.cracking_minutes_used
            >= self.ctx.limits.maximum_cracking_duration_minutes
        ):
            raise ScopeViolation("límite de tiempo de cracking alcanzado")

    def assert_gpu_temperature(self) -> None:
        if self.ctx.usage.current_gpu_temp > self.ctx.limits.maximum_gpu_temperature:
            raise ScopeViolation(
                f"temperatura GPU {self.ctx.usage.current_gpu_temp}°C supera el límite "
                f"{self.ctx.limits.maximum_gpu_temperature}°C"
            )
