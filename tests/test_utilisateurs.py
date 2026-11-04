from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies import get_current_user
from app.main import app
from app.models import Utilisateur
from app.models.enums import Role
from app.security import hasher_mot_de_passe, verifier_mot_de_passe


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    admin = Utilisateur(
        email="admin@example.com",
        nom_complet="Admin",
        mot_de_passe_hash=hasher_mot_de_passe("admin-password"),
        role=Role.admin,
        actif=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    def override_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_admin_can_create_list_read_and_update_user(client, db_session) -> None:
    created = client.post(
        "/api/v1/utilisateurs",
        json={
            "email": " Tailleur@Example.com ",
            "nom_complet": "  Awa Diallo  ",
            "mot_de_passe": "tailleur-password",
            "role": "tailleur",
        },
    )

    assert created.status_code == 201
    body = created.json()
    assert body["email"] == "tailleur@example.com"
    assert body["nom_complet"] == "Awa Diallo"
    assert body["role"] == "tailleur"
    assert "mot_de_passe_hash" not in body
    user_id = body["id"]

    listed = client.get("/api/v1/utilisateurs")
    read = client.get(f"/api/v1/utilisateurs/{user_id}")
    updated = client.patch(
        f"/api/v1/utilisateurs/{user_id}",
        json={"nom_complet": "Awa D.", "mot_de_passe": "new-password"},
    )

    assert listed.status_code == 200
    assert [user["email"] for user in listed.json()] == [
        "admin@example.com",
        "tailleur@example.com",
    ]
    assert read.status_code == 200
    assert read.json()["id"] == user_id
    assert updated.status_code == 200
    assert updated.json()["nom_complet"] == "Awa D."
    stored_user = db_session.scalar(
        select(Utilisateur).where(Utilisateur.id == user_id)
    )
    assert stored_user is not None
    assert verifier_mot_de_passe("new-password", stored_user.mot_de_passe_hash)


def test_user_management_requires_admin(client, monkeypatch) -> None:
    tailor = Utilisateur(
        id=99,
        email="tailleur@example.com",
        nom_complet="Tailleur",
        mot_de_passe_hash="unused",
        role=Role.tailleur,
        actif=True,
    )
    monkeypatch.setitem(
        app.dependency_overrides, get_current_user, lambda: tailor
    )

    response = client.get("/api/v1/utilisateurs")

    assert response.status_code == 403
    assert response.json() == {"detail": "Droits insuffisants pour cette action"}


def test_duplicate_user_email_returns_conflict(client) -> None:
    response = client.post(
        "/api/v1/utilisateurs",
        json={
            "email": "admin@example.com",
            "nom_complet": "Autre",
            "mot_de_passe": "some-password",
            "role": "admin",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Un compte existe déjà avec cet email"
    }


def test_missing_user_returns_404(client) -> None:
    response = client.get("/api/v1/utilisateurs/9999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Utilisateur introuvable"}


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        (
            {"actif": False},
            "Un administrateur ne peut pas désactiver son propre compte",
        ),
        (
            {"role": "tailleur"},
            "Un administrateur ne peut pas retirer son propre rôle admin",
        ),
    ],
)
def test_admin_cannot_disable_or_demote_self(
    client, db_session, payload, detail
) -> None:
    admin = db_session.scalar(
        select(Utilisateur).where(Utilisateur.email == "admin@example.com")
    )
    assert admin is not None

    response = client.patch(
        f"/api/v1/utilisateurs/{admin.id}",
        json=payload,
    )

    assert response.status_code == 409
    assert response.json() == {"detail": detail}


def test_user_update_ignores_null_fields_and_allows_admin_password_change(
    client, db_session
) -> None:
    admin = db_session.scalar(
        select(Utilisateur).where(Utilisateur.email == "admin@example.com")
    )
    assert admin is not None

    response = client.patch(
        f"/api/v1/utilisateurs/{admin.id}",
        json={
            "nom_complet": None,
            "role": None,
            "actif": None,
            "mot_de_passe": "new-admin-password",
        },
    )

    assert response.status_code == 200
    assert response.json()["nom_complet"] == "Admin"
    assert response.json()["role"] == "admin"
    assert response.json()["actif"] is True
    assert verifier_mot_de_passe("new-admin-password", admin.mot_de_passe_hash)
