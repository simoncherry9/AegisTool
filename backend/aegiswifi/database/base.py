"""Base declarativa de SQLAlchemy y mixins reutilizables."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Raíz declarativa de todos los modelos de AegisWiFi."""


class TimestampMixin:
    """Añade ``created_at`` / ``updated_at`` con defaults de Python (client-side)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
