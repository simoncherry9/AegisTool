"""Modelos de dominio (minuta §28).

Estados y niveles representados como ``enum.StrEnum`` y almacenados en columnas
``String`` (sencillo para SQLite/migraciones; la validación fina vive en los DTOs
Pydantic de cada módulo, en ``*/schemas.py``).

Relaciones:
    Engagement 1──* ScopeTarget
    Engagement 1──* AccessPoint
    Engagement 1──* Capture
    Engagement 1──* Finding
    Engagement 1──* Job
    Job         1──* JobEventLog
    AccessPoint 1──* HandshakeArtifact
    Station     1──* HandshakeArtifact
    Capture     1──* HandshakeArtifact
    HandshakeArtifact 1──1 CrackingJob (opcional)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aegiswifi.database.base import Base, TimestampMixin

# --- Enums (minuta §11, §15, §18, §26, §29) ---------------------------------


class EngagementStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class JobStatus(StrEnum):
    CREATED = "CREATED"
    VALIDATING_SCOPE = "VALIDATING_SCOPE"
    QUEUED = "QUEUED"
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    WAITING_FOR_EVIDENCE = "WAITING_FOR_EVIDENCE"
    PAUSED = "PAUSED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    RESOURCE_LIMITED = "RESOURCE_LIMITED"


class CrackJobStatus(StrEnum):
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RESTORING = "RESTORING"
    RECOVERED = "RECOVERED"
    EXHAUSTED = "EXHAUSTED"
    TIME_LIMIT_REACHED = "TIME_LIMIT_REACHED"
    RESOURCE_LIMIT_REACHED = "RESOURCE_LIMIT_REACHED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class HandshakeQuality(StrEnum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    ACCEPTABLE = "ACCEPTABLE"
    POOR = "POOR"
    INVALID = "INVALID"


class Severity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FindingStatus(StrEnum):
    OPEN = "OPEN"
    CONFIRMED = "CONFIRMED"
    REMEDIATED = "REMEDIATED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    ACCEPTED_RISK = "ACCEPTED_RISK"


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    AUDITOR = "AUDITOR"


# --- Entidades (minuta §28) --------------------------------------------------


class User(TimestampMixin, Base):
    """Usuario del sistema para autenticación y asignación de engagements."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default=UserRole.OPERATOR)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Engagement(TimestampMixin, Base):
    """Auditoría como entidad independiente (minuta §11, §28)."""

    __tablename__ = "engagements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False
    )  # p. ej. ENG-2026-001
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    client: Mapped[str] = mapped_column(String(255), nullable=False)
    operator: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=EngagementStatus.DRAFT, index=True
    )
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authorization_reference: Mapped[str | None] = mapped_column(String(255))
    permissions: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    limits: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    operator_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    operator_user: Mapped[User | None] = relationship("User")

    jobs: Mapped[list[Job]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    scope_targets: Mapped[list[ScopeTarget]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    access_points: Mapped[list[AccessPoint]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    captures: Mapped[list[Capture]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    findings: Mapped[list[Finding]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )


class ScopeTarget(Base):
    """Objetivo dentro del alcance autorizado de un engagement (minuta §12, §28)."""

    __tablename__ = "scope_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ssid: Mapped[str | None] = mapped_column(String(64))
    bssid: Mapped[str | None] = mapped_column(String(17), index=True)
    channel: Mapped[int | None] = mapped_column(Integer)
    band: Mapped[str | None] = mapped_column(String(8))  # "2.4" | "5" | "6"
    permission_level: Mapped[str] = mapped_column(String(32), default="passive")
    notes: Mapped[str | None] = mapped_column(Text)

    engagement: Mapped[Engagement] = relationship(back_populates="scope_targets")


class AccessPoint(Base):
    """Punto de acceso detectado (minuta §14, §28)."""

    __tablename__ = "access_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ssid: Mapped[str | None] = mapped_column(String(64))
    bssid: Mapped[str] = mapped_column(String(17), nullable=False, index=True)
    vendor: Mapped[str | None] = mapped_column(String(128))
    channel: Mapped[int | None] = mapped_column(Integer)
    frequency: Mapped[int | None] = mapped_column(Integer)  # MHz
    signal: Mapped[int | None] = mapped_column(Integer)  # dBm
    protocol: Mapped[str | None] = mapped_column(String(16))  # WPA/WPA2/WPA3/OPEN
    akm: Mapped[str | None] = mapped_column(String(64))
    cipher: Mapped[str | None] = mapped_column(String(32))
    pmf: Mapped[str | None] = mapped_column(String(16))  # disabled|optional|required
    wps: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    engagement: Mapped[Engagement] = relationship(back_populates="access_points")
    handshake_artifacts: Mapped[list[HandshakeArtifact]] = relationship(
        back_populates="access_point"
    )


class Station(Base):
    """Cliente inalámbrico detectado (minuta §14, §28)."""

    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mac: Mapped[str] = mapped_column(String(17), nullable=False, index=True)
    randomized: Mapped[bool] = mapped_column(Boolean, default=False)
    vendor: Mapped[str | None] = mapped_column(String(128))
    associated_bssid: Mapped[str | None] = mapped_column(String(17), index=True)
    signal: Mapped[int | None] = mapped_column(Integer)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    controlled: Mapped[bool] = mapped_column(Boolean, default=False)

    handshake_artifacts: Mapped[list[HandshakeArtifact]] = relationship(back_populates="station")


class Capture(TimestampMixin, Base):
    """Archivo de captura/evidencia asociado a un engagement y opcionalmente a un trabajo (minuta §30)."""

    __tablename__ = "captures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[str] = mapped_column(String(32), default="original", index=True)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    format: Mapped[str] = mapped_column(
        String(16), default="pcapng"
    )  # pcap|pcapng|kismet|log|22000|txt
    sha256: Mapped[str | None] = mapped_column(String(64))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    interface: Mapped[str | None] = mapped_column(String(32))
    channel: Mapped[int | None] = mapped_column(Integer)
    bssid: Mapped[str | None] = mapped_column(String(17))
    ssid: Mapped[str | None] = mapped_column(String(64))
    tool: Mapped[str | None] = mapped_column(String(64))
    tool_version: Mapped[str | None] = mapped_column(String(64))
    extra_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    derived_from_id: Mapped[int | None] = mapped_column(
        ForeignKey("captures.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    engagement: Mapped[Engagement] = relationship(back_populates="captures")
    job: Mapped[Job | None] = relationship(back_populates="evidence")
    handshake_artifacts: Mapped[list[HandshakeArtifact]] = relationship(back_populates="capture")
    derived_from: Mapped[Capture | None] = relationship(remote_side="Capture.id", post_update=True)


class HandshakeArtifact(TimestampMixin, Base):
    """Handshake EAPOL o PMKID validado y convertible a formato 22000 (§15, §16, §28)."""

    __tablename__ = "handshake_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    access_point_id: Mapped[int | None] = mapped_column(
        ForeignKey("access_points.id", ondelete="SET NULL"), index=True
    )
    station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id", ondelete="SET NULL"), index=True
    )
    capture_id: Mapped[int | None] = mapped_column(
        ForeignKey("captures.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16), default="eapol")  # eapol|pmkid
    message_pair: Mapped[str | None] = mapped_column(String(16))  # p. ej. M1M2, M1M4
    quality: Mapped[str] = mapped_column(String(32), default=HandshakeQuality.INVALID)
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    hash22000_path: Mapped[str | None] = mapped_column(String(512))

    access_point: Mapped[AccessPoint | None] = relationship(back_populates="handshake_artifacts")
    station: Mapped[Station | None] = relationship(back_populates="handshake_artifacts")
    capture: Mapped[Capture | None] = relationship(back_populates="handshake_artifacts")
    cracking_job: Mapped[CrackingJob | None] = relationship(
        back_populates="artifact", uselist=False
    )


class CrackingJob(TimestampMixin, Base):
    """Trabajo de auditoría de contraseña con Hashcat (minuta §18, §28)."""

    __tablename__ = "cracking_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artifact_id: Mapped[int | None] = mapped_column(
        ForeignKey("handshake_artifacts.id", ondelete="SET NULL"), index=True
    )
    strategy: Mapped[str] = mapped_column(String(32))  # dictionary|mask|hybrid…
    keyspace: Mapped[int | None] = mapped_column(Integer)
    progress: Mapped[float | None] = mapped_column(Float)  # 0..1
    speed: Mapped[int | None] = mapped_column(Integer)  # H/s
    status: Mapped[str] = mapped_column(String(32), default=CrackJobStatus.CREATED, index=True)
    recovered: Mapped[bool] = mapped_column(Boolean, default=False)
    encrypted_secret: Mapped[str | None] = mapped_column(Text)  # Fernet token
    restore_path: Mapped[str | None] = mapped_column(String(512))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    artifact: Mapped[HandshakeArtifact | None] = relationship(back_populates="cracking_job")


class Finding(TimestampMixin, Base):
    """Hallazgo profesional generado por el motor de hallazgos (minuta §29, §28)."""

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)  # WIFI-PSK, WIFI-WPS…
    rule_id: Mapped[str | None] = mapped_column(String(64))  # p. ej. WIFI-PSK-001
    severity: Mapped[str] = mapped_column(String(16), default=Severity.INFO, index=True)
    confidence: Mapped[float | None] = mapped_column(Float)  # 0..1
    description: Mapped[str | None] = mapped_column(Text)
    impact: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    remediation: Mapped[str | None] = mapped_column(Text)
    affected_assets: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default=FindingStatus.OPEN, index=True)

    engagement: Mapped[Engagement] = relationship(back_populates="findings")


class Job(TimestampMixin, Base):
    """Trabajo persistente del sistema de auditoría (minuta §26)."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # passive_capture, handshake_capture, password_audit...
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=JobStatus.CREATED, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[float | None] = mapped_column(Float)  # 0..1, None = indeterminado
    group_id: Mapped[str | None] = mapped_column(
        String(64), index=True
    )  # grupo de procesos coordinados
    error_message: Mapped[str | None] = mapped_column(Text)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)
    worker_pid: Mapped[int | None] = mapped_column(Integer)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parameters: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    result_summary: Mapped[dict[str, object] | None] = mapped_column(JSON)
    log_path: Mapped[str | None] = mapped_column(String(512))
    sha256: Mapped[str | None] = mapped_column(String(64))

    engagement: Mapped[Engagement] = relationship(back_populates="jobs")
    event_logs: Mapped[list[JobEventLog]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    evidence: Mapped[list[Capture]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class JobEventLog(TimestampMixin, Base):
    """Registro de cambio de estado de un trabajo (minuta §26)."""

    __tablename__ = "job_event_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(32))  # None en creación
    to_status: Mapped[str | None] = mapped_column(String(32))
    message: Mapped[str | None] = mapped_column(Text)

    job: Mapped[Job] = relationship(back_populates="event_logs")


# --- Índices adicionales -----------------------------------------------------

Index("ix_scope_targets_engagement_ssid", ScopeTarget.engagement_id, ScopeTarget.ssid)
Index("ix_access_points_engagement_bssid", AccessPoint.engagement_id, AccessPoint.bssid)
Index("ix_jobs_engagement_status", Job.engagement_id, Job.status)
Index("ix_job_event_logs_job_created", JobEventLog.job_id, JobEventLog.created_at)
Index("ix_captures_engagement_job", Capture.engagement_id, Capture.job_id)
Index("ix_captures_job_category", Capture.job_id, Capture.category)
