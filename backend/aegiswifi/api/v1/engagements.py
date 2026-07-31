"""Router REST de engagements (minuta §11, §32 página Engagements)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from aegiswifi.database.engine import get_db
from aegiswifi.engagements import service
from aegiswifi.engagements.schemas import (
    EngagementCreate,
    EngagementRead,
    EngagementUpdate,
)

router = APIRouter(prefix="/engagements", tags=["engagements"])


@router.get("", response_model=list[EngagementRead])
def list_engagements(db: Session = Depends(get_db)) -> list[EngagementRead]:
    return [EngagementRead.model_validate(e) for e in service.list_engagements(db)]


@router.post("", response_model=EngagementRead, status_code=status.HTTP_201_CREATED)
def create_engagement(payload: EngagementCreate, db: Session = Depends(get_db)) -> EngagementRead:
    return EngagementRead.model_validate(service.create_engagement(db, payload))


@router.get("/{engagement_id}", response_model=EngagementRead)
def get_engagement(engagement_id: int, db: Session = Depends(get_db)) -> EngagementRead:
    return EngagementRead.model_validate(service.get_engagement(db, engagement_id))


@router.patch("/{engagement_id}", response_model=EngagementRead)
def update_engagement(
    engagement_id: int,
    payload: EngagementUpdate,
    db: Session = Depends(get_db),
) -> EngagementRead:
    return EngagementRead.model_validate(service.update_engagement(db, engagement_id, payload))


@router.post("/{engagement_id}/activate", response_model=EngagementRead)
def activate(engagement_id: int, db: Session = Depends(get_db)) -> EngagementRead:
    return EngagementRead.model_validate(service.activate(db, engagement_id))


@router.post("/{engagement_id}/close", response_model=EngagementRead)
def close(engagement_id: int, db: Session = Depends(get_db)) -> EngagementRead:
    return EngagementRead.model_validate(service.close(db, engagement_id))
