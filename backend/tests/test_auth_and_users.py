"""Tests de autenticación JWT y gestión de usuarios."""

from __future__ import annotations

import pytest
from aegiswifi.database.models import User, UserRole
from aegiswifi.users import service
from aegiswifi.users.schemas import UserCreate, UserUpdate


def test_user_creation_and_auth(db_session):
    # Crear usuario
    payload = UserCreate(
        username="testop",
        email="testop@aegiswifi.local",
        full_name="Test Operator",
        password="secretpassword",
        role=UserRole.OPERATOR,
    )
    user = service.create_user(db_session, payload)
    assert user.id is not None
    assert user.username == "testop"
    assert user.role == UserRole.OPERATOR

    # Autenticar con clave correcta
    auth_user = service.authenticate_user(db_session, "testop", "secretpassword")
    assert auth_user.id == user.id

    # Autenticar con clave incorrecta
    with pytest.raises(service.AuthenticationError):
        service.authenticate_user(db_session, "testop", "wrongpass")


def test_duplicate_user_fails(db_session):
    payload = UserCreate(
        username="dupuser",
        email="dup@aegiswifi.local",
        full_name="Dup User",
        password="password123",
    )
    service.create_user(db_session, payload)

    with pytest.raises(service.UserAlreadyExistsError):
        service.create_user(db_session, payload)


def test_auth_api_endpoints(client, db_session):
    # Crear admin inicial
    admin = service.seed_default_admin(db_session)
    assert admin.username == "admin"

    # Login exitoso vía API
    login_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "access_token" in data
    token = data["access_token"]

    # Obtenerme (/auth/me) con token Bearer
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "admin"

    # Crear nuevo usuario operador vía API /users
    new_user_resp = client.post(
        "/api/v1/users",
        json={
            "username": "op2",
            "email": "op2@test.local",
            "full_name": "Operator Two",
            "password": "password123",
            "role": "OPERATOR",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert new_user_resp.status_code == 201
    assert new_user_resp.json()["username"] == "op2"

    # Listar usuarios
    list_resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 2
