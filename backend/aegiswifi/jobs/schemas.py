"""DTOs Pydantic para el sistema de trabajos (minuta §26, §28)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aegiswifi.database.models import JobStatus


class JobBase(BaseModel):
    engagement_id: int = Field(..., ge=1)
    kind: str = Field(..., min_length=1, max_length=64)
    priority: int = Field(default=0, ge=-10, le=10)
    timeout_seconds: int = Field(default=300, ge=30, le=86400)
    parameters: dict[str, object] = Field(default_factory=dict)

    @classmethod
    def _known_kinds(cls) -> set[str]:
        return {
            "passive_capture",
            "handshake_capture",
            "pmkid_capture",
            "controlled_reconnect",
            "password_audit",
            "wps_testing",
            "enterprise_testing",
            "denial_of_service",
            "protocol_fuzzing",
            "isolation_test",
            "rogue_ap_detection",
        }


class JobCreate(JobBase):
    """DTO para creación de un trabajo."""

    pass


class JobUpdate(BaseModel):
    """DTO para actualización parcial de un trabajo."""

    status: JobStatus | None = None
    progress: float | None = Field(default=None, ge=0.0, le=1.0)
    error_message: str | None = None
    result_summary: dict[str, object] | None = None
    worker_pid: int | None = None
    heartbeat_at: datetime | None = None
    group_id: str | None = None


class JobStatusUpdate(BaseModel):
    """DTO para transición explícita de estado."""

    status: JobStatus
    message: str | None = None


class JobRead(BaseModel):
    """DTO completo de lectura de un trabajo."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    engagement_id: int
    kind: str
    status: JobStatus
    priority: int
    progress: float | None
    group_id: str | None
    error_message: str | None
    timeout_seconds: int
    worker_pid: int | None
    heartbeat_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    parameters: dict[str, object]
    result_summary: dict[str, object] | None
    log_path: str | None
    sha256: str | None
    created_at: datetime
    updated_at: datetime


class JobListRead(BaseModel):
    """DTO ligero para listados de trabajos."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    engagement_id: int
    kind: str
    status: JobStatus
    priority: int
    progress: float | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class JobEventLogRead(BaseModel):
    """DTO de lectura de un evento de cambio de estado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    from_status: str | None
    to_status: str | None
    message: str | None
    created_at: datetime
