"""Router REST de usuarios (gestión de operadores y administración)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aegiswifi.api.v1.auth import require_current_user
from aegiswifi.core.exceptions import AegisError, NotFound
from aegiswifi.database.engine import get_db
from aegiswifi.database.models import User, UserRole
from aegiswifi.users import service
from aegiswifi.users.schemas import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


def require_admin(current_user: User = Depends(require_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de Administrador para esta acción",
        )
    return current_user


@router.get("", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_current_user),
) -> list[UserRead]:
    return [UserRead.model_validate(u) for u in service.list_users(db)]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserRead:
    try:
        user = service.create_user(db, payload)
        return UserRead.model_validate(user)
    except AegisError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_current_user),
) -> UserRead:
    try:
        user = service.get_user_by_id(db, user_id)
        return UserRead.model_validate(user)
    except NotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserRead:
    try:
        user = service.update_user(db, user_id, payload)
        return UserRead.model_validate(user)
    except NotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AegisError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
