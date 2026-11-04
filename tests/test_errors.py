import asyncio

from fastapi import Request
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.exceptions import (
    AccesInterdit,
    Conflit,
    DonneesInvalides,
    ErreurMetier,
    NonTrouve,
)
from app.main import app, gerer_erreur_metier
from app.models.enums import Role

client = TestClient(app)


def test_business_errors_return_unified_detail_shape() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/"})
    errors = [
        (ErreurMetier(418, "Erreur test"), 418),
        (NonTrouve("Introuvable"), 404),
        (Conflit("Conflit"), 409),
        (DonneesInvalides("Données invalides"), 422),
        (AccesInterdit("Accès interdit"), 403),
    ]

    for error, expected_status in errors:
        response = asyncio.run(gerer_erreur_metier(request, error))

        assert response.status_code == expected_status
        assert response.body.decode() == f'{{"detail":"{error.detail}"}}'


def test_request_validation_returns_single_string_detail() -> None:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "not-an-email"},
    )

    assert response.status_code == 422
    assert set(response.json()) == {"detail"}
    assert isinstance(response.json()["detail"], str)


def test_short_password_validation_returns_french_message(monkeypatch) -> None:
    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: type("Admin", (), {"id": 1, "role": Role.admin})(),
    )
    response = client.post(
        "/api/v1/utilisateurs",
        headers={"Authorization": "Bearer test-token"},
        json={
            "email": "new-user@example.com",
            "nom_complet": "Nouvel utilisateur",
            "mot_de_passe": "abc",
            "role": "accueil",
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "mot_de_passe : doit contenir au moins 8 caractère(s)"
    }
    monkeypatch.delitem(app.dependency_overrides, get_current_user)


def test_http_errors_keep_detail_object_shape() -> None:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "unknown@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Email ou mot de passe incorrect"}


def test_not_found_error_keeps_detail_object_shape() -> None:
    response = client.get("/route-inconnue")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
