"""Máquina de estados de trabajos (minuta §26).

Valida transiciones entre estados según el diagrama de §26:

    CREATED → VALIDATING_SCOPE → QUEUED → PREPARING → RUNNING
      → WAITING_FOR_EVIDENCE → COMPLETED (terminal)
      → FAILED, TIMED_OUT, RESOURCE_LIMITED (terminales)
    RUNNING → PAUSED → RUNNING
    RUNNING → CANCELLING → CANCELLED (terminal)
"""

from __future__ import annotations

from aegiswifi.core.exceptions import ValidationFailed
from aegiswifi.database.models import JobStatus


class JobStateMachine:
    """Validación de transiciones de estado. Sin dependencias externas."""

    # Mapa de transiciones válidas: estado_origen → conjunto de destinos permitidos.
    _TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
        JobStatus.CREATED: {JobStatus.VALIDATING_SCOPE, JobStatus.CANCELLING},
        JobStatus.VALIDATING_SCOPE: {JobStatus.QUEUED, JobStatus.FAILED, JobStatus.CANCELLING},
        JobStatus.QUEUED: {JobStatus.PREPARING, JobStatus.CANCELLING, JobStatus.CANCELLED},
        JobStatus.PREPARING: {JobStatus.RUNNING, JobStatus.FAILED, JobStatus.CANCELLING},
        JobStatus.RUNNING: {
            JobStatus.WAITING_FOR_EVIDENCE,
            JobStatus.PAUSED,
            JobStatus.CANCELLING,
            JobStatus.FAILED,
            JobStatus.TIMED_OUT,
            JobStatus.RESOURCE_LIMITED,
        },
        JobStatus.WAITING_FOR_EVIDENCE: {  # noqa: E501
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLING,
        },
        JobStatus.PAUSED: {JobStatus.RUNNING, JobStatus.CANCELLING},
        JobStatus.CANCELLING: {JobStatus.CANCELLED, JobStatus.FAILED},
        JobStatus.FAILED: {JobStatus.CREATED},  # retry
        JobStatus.COMPLETED: set(),
        JobStatus.TIMED_OUT: set(),
        JobStatus.RESOURCE_LIMITED: set(),
        JobStatus.CANCELLED: set(),
    }

    _TERMINAL: frozenset[JobStatus] = frozenset(
        {
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.TIMED_OUT,
            JobStatus.RESOURCE_LIMITED,
            JobStatus.CANCELLED,
        }
    )

    @classmethod
    def is_valid_transition(cls, from_status: JobStatus, to_status: JobStatus) -> bool:
        """Retorna ``True`` si la transición es válida según §26."""
        allowed = cls._TRANSITIONS.get(from_status)
        if allowed is None:
            return False
        return to_status in allowed

    @classmethod
    def assert_valid_transition(cls, from_status: JobStatus, to_status: JobStatus) -> None:
        """Lanza :class:`ValidationFailed` si la transición no es válida."""
        if not cls.is_valid_transition(from_status, to_status):
            raise ValidationFailed(
                f"transición de estado inválida: {from_status.value} → {to_status.value}"
            )

    @classmethod
    def is_terminal(cls, status: JobStatus) -> bool:
        """Retorna ``True`` si el estado es terminal (no admite más transiciones)."""
        return status in cls._TERMINAL

    @classmethod
    def requires_scope_check(cls, from_status: JobStatus, to_status: JobStatus) -> bool:
        """Retorna ``True`` si la transición requiere validación de alcance."""
        return from_status == JobStatus.CREATED and to_status == JobStatus.VALIDATING_SCOPE
