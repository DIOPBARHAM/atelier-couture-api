from datetime import datetime, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.dependencies import exiger_roles
from app.main import app
from app.models import Utilisateur
from app.models.enums import Role
from app.services import auth_service

client = TestClient(app)


def make_user(*, active: bool = True) -> Utilisateur:
    return Utilisateur(
        id=1,
        email="admin@atelier.sn",
        nom_complet="Admin Atelier",
        mot_de_passe_hash="hashed",
        role=Role.admin,
        actif=active,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_login_returns_bearer_token_for_valid_credentials(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_service, "authentifier", lambda db, email, password: make_user()
    )

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@atelier.sn", "password": "valid-password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.access_token_expire_minutes * 60
    assert jwt.decode(
        body["access_token"],
        settings.secret_key,
        algorithms=[settings.algorithm],
    )["sub"] == "1"


def test_login_returns_same_generic_error_for_invalid_credentials(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_service, "authentifier", lambda db, email, password: None
    )

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "unknown@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Email ou mot de passe incorrect"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_requires_authentication() -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_returns_current_user_without_password_hash(monkeypatch) -> None:
    user = make_user()

    class UserSession:
        def get(self, model, user_id):
            assert model is Utilisateur
            assert user_id == user.id
            return user

    monkeypatch.setitem(
        app.dependency_overrides, get_db, lambda: UserSession()
    )
    token = jwt.encode(
        {"sub": str(user.id)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == user.email
    assert body["role"] == "admin"
    assert "mot_de_passe_hash" not in body


@pytest.mark.parametrize(
    ("token", "active", "expected_detail"),
    [
        ("invalid-token", True, "Jeton invalide ou expiré : reconnectez-vous"),
        (None, False, "Compte désactivé ou inexistant"),
    ],
)
def test_me_rejects_invalid_tokens_and_inactive_accounts(
    monkeypatch, token, active, expected_detail
) -> None:
    user = make_user(active=active)

    class UserSession:
        def get(self, model, user_id):
            return user

    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: UserSession())
    headers = {}
    if token is None:
        signed_token = jwt.encode(
            {"sub": str(user.id)},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        headers["Authorization"] = f"Bearer {signed_token}"
    else:
        headers["Authorization"] = f"Bearer {token}"

    response = client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": expected_detail}


def test_authentication_service_normalizes_email_and_rejects_inactive_user(
    monkeypatch,
) -> None:
    user = make_user(active=False)
    seen_statement = None

    class UserSession:
        def scalar(self, statement):
            nonlocal seen_statement
            assert list(statement.compile().params.values()) == [
                "admin@atelier.sn"
            ]
            seen_statement = statement
            return user

    monkeypatch.setattr(
        "app.services.auth_service.verifier_mot_de_passe",
        lambda password, stored_hash: password == "valid-password",
    )

    result = auth_service.authentifier(
        UserSession(), "  ADMIN@ATELIER.SN ", "valid-password"
    )

    assert result is None
    assert seen_statement is not None


def test_authentication_service_rejects_unknown_user_and_wrong_password(
    monkeypatch,
) -> None:
    user = make_user()

    class UserSession:
        result = user

        def scalar(self, statement):
            return self.result

    db = UserSession()
    monkeypatch.setattr(
        "app.services.auth_service.verifier_mot_de_passe",
        lambda password, stored_hash: False,
    )
    assert auth_service.authentifier(db, user.email, "wrong-password") is None

    db.result = None
    assert auth_service.authentifier(db, "unknown@example.com", "password") is None


def test_role_dependency_allows_listed_role_and_rejects_other_roles() -> None:
    verify_admin = exiger_roles(Role.admin)
    admin = make_user()
    tailor = make_user()
    tailor.role = Role.tailleur

    assert verify_admin(admin) is admin
    with pytest.raises(HTTPException) as error:
        verify_admin(tailor)

    assert error.value.status_code == 403
