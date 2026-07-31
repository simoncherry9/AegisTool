"""Servicio de dominio para gestión de usuarios y autenticación."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegiswifi.core.exceptions import AegisError, EntityNotFoundError
from aegiswifi.core.security import hash_password, verify_password
from aegiswifi.database.models import User, UserRole
from aegiswifi.users.schemas import UserCreate, UserUpdate


class AuthenticationError(AegisError):
    """Error de autenticación (credenciales inválidas o usuario inactivo)."""

    def __init__(self, message: str = "Credenciales inválidas"):
        super().__init__(message)


class UserAlreadyExistsError(AegisError):
    """El nombre de usuario o email ya está en uso."""

    def __init__(self, field: str, value: str):
        super().__init__(f"El {field} '{value}' ya se encuentra registrado.")


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)).all())


def get_user_by_id(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if not user:
        raise EntityNotFoundError(f"Usuario {user_id} no encontrado")
    return user


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def create_user(db: Session, payload: UserCreate) -> User:
    if get_user_by_username(db, payload.username):
        raise UserAlreadyExistsError("nombre de usuario", payload.username)
    if db.scalar(select(User).where(User.email == payload.email)):
        raise UserAlreadyExistsError("email", payload.email)

    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user_id: int, payload: UserUpdate) -> User:
    user = get_user_by_id(db, user_id)
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.email is not None:
        user.email = payload.email
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)

    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User:
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        raise AuthenticationError("Nombre de usuario o contraseña incorrectos.")
    if not user.is_active:
        raise AuthenticationError("La cuenta de usuario se encuentra desactivada.")
    return user


def seed_default_admin(db: Session) -> User:
    """Crea el usuario admin por defecto si la tabla está vacía."""
    existing_admin = get_user_by_username(db, "admin")
    if existing_admin:
        return existing_admin

    admin_payload = UserCreate(
        username="admin",
        email="admin@aegiswifi.local",
        full_name="Administrador AegisWiFi",
        password="admin123",
        role=UserRole.ADMIN,
    )
    return create_user(db, admin_payload)
