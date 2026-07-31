"""DTOs Pydantic para engagements (minuta §11, §28)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aegiswifi.database.models import EngagementStatus


class EngagementBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    client: str = Field(..., min_length=1, max_length=255)
    operator: str = Field(..., min_length=1, max_length=255)
    start_date: datetime | None = None
    end_date: datetime | None = None
    authorization_reference: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    permissions: dict[str, object] = Field(default_factory=dict)
    limits: dict[str, object] = Field(default_factory=dict)


class EngagementCreate(EngagementBase):
    pass


class EngagementUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = None
    status: EngagementStatus | None = None
    end_date: datetime | None = None


class EngagementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    client: str
    operator: str
    status: EngagementStatus
    start_date: datetime | None
    end_date: datetime | None
    authorization_reference: str | None
    permissions: dict[str, object]
    limits: dict[str, object]
    notes: str | None
    created_at: datetime
    updated_at: datetime
