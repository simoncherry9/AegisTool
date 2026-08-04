"""Router REST de autenticación y sesión."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from aegiswifi.core.config import get_settings
from aegiswifi.core.security import create_access_token, decode_access_token
from aegiswifi.database.engine import get_db
from aegiswifi.database.models import User
from aegiswifi.users import service
from aegiswifi.users.schemas import LoginRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    try:
        user_id = int(str(payload["sub"]))
        user = db.get(User, user_id)
        if user and user.is_active:
            return user
    except ValueError:
        pass
    return None


def require_current_user(user: User | None = Depends(get_current_user)) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado o token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_api_user(user: User | None = Depends(get_current_user)) -> User | None:
    """Protege la API cuando la autenticación está habilitada.

    El bypass existe exclusivamente para instalaciones y tests que configuran
    explícitamente ``security.require_auth=false``.
    """
    if not get_settings().security.require_auth:
        return user
    return require_current_user(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user = service.authenticate_user(db, payload.username, payload.password)
        token = create_access_token(user.id, user.username, user.role)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserRead.model_validate(user),
        )
    except service.AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(require_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
