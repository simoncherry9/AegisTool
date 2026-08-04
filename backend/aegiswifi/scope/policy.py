"""Policy Engine — autoriza o bloquea cada acción.

El PolicyEngine es el guardián del sistema. Antes de cualquier acción activa,
cada módulo debe invocar PolicyEngine.assert_allowed con el contexto correspondiente.

En desarrollo puede desactivarse explícitamente mediante:

    AEGIS_ENV=development
    AEGIS_POLICY_ENFORCEMENT=false

Fuera del entorno development, cualquier intento de desactivarlo genera un error.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime

from aegiswifi.core.exceptions import ScopeViolation
from aegiswifi.scope.schemas import Limits, Permissions, ScopeBlock


_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}


def _read_boolean_env(name: str, *, default: bool) -> bool:
    """Lee una variable de entorno booleana de forma estricta."""

    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()

    if normalized in _TRUE_VALUES:
        return True

    if normalized in _FALSE_VALUES:
        return False

    raise RuntimeError(
        f"valor inválido para {name}: {raw_value!r}. "
        f"Valores válidos: {sorted(_TRUE_VALUES | _FALSE_VALUES)}"
    )


def resolve_policy_enforcement() -> bool:
    """Determina si el PolicyEngine debe aplicar sus controles.

    Reglas:
      - Por defecto, las políticas están activadas.
      - Solo pueden desactivarse con AEGIS_ENV=development.
      - En test también permanecen activadas salvo que se inyecte explícitamente
        enforcement_enabled=False al construir PolicyEngine.
      - Nunca se permite desactivarlas por variable de entorno en producción.
    """

    environment = os.getenv("AEGIS_ENV", "production").strip().lower()

    enforcement_enabled = _read_boolean_env(
        "AEGIS_POLICY_ENFORCEMENT",
        default=True,
    )

    if not enforcement_enabled and environment != "development":
        raise RuntimeError(
            "No se puede desactivar el PolicyEngine fuera de development. "
            "Definí AEGIS_ENV=development para usar el modo permisivo."
        )

    return enforcement_enabled


@dataclass
class Usage:
    """Contadores actuales del engagement, administrados por el JobManager."""

    active_frames_sent: int = 0
    cracking_minutes_used: int = 0
    current_gpu_temp: int = 0


@dataclass
class ScopeContext:
    """Contexto de alcance resuelto para un engagement activo."""

    engagement_code: str
    valid_from: datetime
    valid_until: datetime
    scope: ScopeBlock
    permissions: Permissions
    limits: Limits
    operator: str
    usage: Usage = field(default_factory=Usage)

    def is_temporally_valid(self, now: datetime | None = None) -> bool:
        """Comprueba que el engagement esté dentro de su ventana temporal."""

        now = now or datetime.now(UTC)

        valid_from = self._ensure_utc(self.valid_from)
        valid_until = self._ensure_utc(self.valid_until)
        current_time = self._ensure_utc(now)

        return valid_from <= current_time <= valid_until

    def is_target_in_scope(
        self,
        *,
        ssid: str | None = None,
        bssid: str | None = None,
        client: str | None = None,
    ) -> bool:
        """Comprueba que el objetivo esté dentro del alcance autorizado."""

        has_explicit_targets = bool(
            self.scope.allowed_ssids
            or self.scope.allowed_bssids
            or self.scope.allowed_clients
        )

        if not has_explicit_targets:
            # Conserva el comportamiento original:
            # sin listas explícitas, cualquier objetivo queda permitido.
            return True

        if (
            ssid is not None
            and self.scope.allowed_ssids
            and ssid not in self.scope.allowed_ssids
        ):
            return False

        if (
            bssid is not None
            and self.scope.allowed_bssids
            and bssid not in self.scope.allowed_bssids
        ):
            return False

        if (
            client is not None
            and self.scope.allowed_clients
            and client not in self.scope.allowed_clients
        ):
            return False

        return True

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        """Normaliza fechas ingenuas o con zona horaria a UTC."""

        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)


class PolicyEngine:
    """Aplica las validaciones antes de ejecutar una acción."""

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

    def __init__(
        self,
        context: ScopeContext,
        *,
        enforcement_enabled: bool | None = None,
    ) -> None:
        """Inicializa el motor de políticas.

        Args:
            context:
                Contexto de alcance del engagement.

            enforcement_enabled:
                - None: resuelve el valor desde las variables de entorno.
                - True: aplica todas las políticas.
                - False: desactiva las políticas para desarrollo o tests.

        Importante:
            La validación de entorno se aplica cuando el valor se obtiene desde
            las variables de entorno. La inyección explícita de False está pensada
            para pruebas unitarias controladas.
        """

        self.ctx = context

        if enforcement_enabled is None:
            self.enforcement_enabled = resolve_policy_enforcement()
        else:
            self.enforcement_enabled = enforcement_enabled

    @property
    def is_enforcing(self) -> bool:
        """Indica si el motor está aplicando las políticas."""

        return self.enforcement_enabled

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
        """Valida una acción activa.

        Cuando enforcement_enabled=False, la acción queda permitida sin ejecutar
        controles de fecha, objetivo, permiso, canal o banda.
        """

        if not self.enforcement_enabled:
            return

        self._assert_temporal()

        self._assert_target(
            ssid=ssid,
            bssid=bssid,
            client=client,
        )

        self._assert_permitted(action)

        self._assert_channel(channel)
        self._assert_band(band)

    def _assert_temporal(self) -> None:
        """Comprueba la ventana temporal del engagement."""

        if not self.ctx.is_temporally_valid():
            raise ScopeViolation(
                f"engagement {self.ctx.engagement_code} fuera de su ventana temporal"
            )

    def _assert_target(
        self,
        *,
        ssid: str | None,
        bssid: str | None,
        client: str | None,
    ) -> None:
        """Comprueba que el objetivo esté autorizado."""

        if not self.ctx.is_target_in_scope(
            ssid=ssid,
            bssid=bssid,
            client=client,
        ):
            raise ScopeViolation(
                "objetivo fuera del alcance "
                f"(ssid={ssid}, bssid={bssid}, client={client})"
            )

    def _assert_permitted(self, action: str) -> None:
        """Comprueba que la acción esté reconocida y permitida."""

        field_name = self._PERMISSION_FIELD.get(action)

        if field_name is None:
            raise ScopeViolation(
                f"acción desconocida para el PolicyEngine: {action}"
            )

        allowed = getattr(self.ctx.permissions, field_name, False)

        if not allowed:
            raise ScopeViolation(
                f"permiso '{action}' no concedido para este engagement"
            )

    def _assert_channel(self, channel: int | None) -> None:
        """Comprueba que el canal esté incluido en el alcance."""

        if channel is None:
            return

        if self.ctx.scope.channels and channel not in self.ctx.scope.channels:
            raise ScopeViolation(f"canal {channel} fuera del alcance")

    def _assert_band(self, band: str | None) -> None:
        """Comprueba que la banda esté incluida en el alcance."""

        if band is None:
            return

        if self.ctx.scope.bands and band not in self.ctx.scope.bands:
            raise ScopeViolation(f"banda {band} fuera del alcance")

    def assert_within_frame_budget(self) -> None:
        """Comprueba el límite de tramas activas."""

        if not self.enforcement_enabled:
            return

        maximum = self.ctx.limits.maximum_active_frames
        current = self.ctx.usage.active_frames_sent

        if current >= maximum:
            raise ScopeViolation(
                f"límite de tramas activas alcanzado ({maximum})"
            )

    def assert_within_cracking_budget(self) -> None:
        """Comprueba el límite temporal de auditoría de contraseñas."""

        if not self.enforcement_enabled:
            return

        maximum = self.ctx.limits.maximum_cracking_duration_minutes
        current = self.ctx.usage.cracking_minutes_used

        if current >= maximum:
            raise ScopeViolation(
                "límite de tiempo de cracking alcanzado "
                f"({current}/{maximum} minutos)"
            )

    def assert_gpu_temperature(self) -> None:
        """Comprueba que la temperatura de la GPU no supere el límite."""

        if not self.enforcement_enabled:
            return

        maximum = self.ctx.limits.maximum_gpu_temperature
        current = self.ctx.usage.current_gpu_temp

        if current > maximum:
            raise ScopeViolation(
                f"temperatura GPU {current}°C supera el límite {maximum}°C"
            )