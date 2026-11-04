from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies import get_current_user
from app.main import app
from app.models import TypeVetement, Utilisateur
from app.models.enums import Role


@pytest.fixture
def catalogue_session() -> Iterator[Session]:
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
def admin_client(catalogue_session: Session) -> Iterator[TestClient]:
    admin = Utilisateur(
        email="admin@example.com",
        nom_complet="Admin",
        mot_de_passe_hash="unused",
        role=Role.admin,
        actif=True,
    )
    catalogue_session.add(admin)
    catalogue_session.commit()
    app.dependency_overrides[get_db] = lambda: catalogue_session
    app.dependency_overrides[get_current_user] = lambda: admin
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_admin_can_create_and_read_catalogue_item(admin_client: TestClient) -> None:
    response = admin_client.post(
        "/api/v1/catalogue",
        json={
            "nom": "  Robe ",
            "description": "Robe sur mesure",
            "prix_base": 30000,
            "delai_jours": 7,
        },
    )

    assert response.status_code == 201
    assert response.json()["nom"] == "Robe"
    prestation_id = response.json()["id"]
    read = admin_client.get(f"/api/v1/catalogue/{prestation_id}")
    assert read.status_code == 200
    assert read.json()["description"] == "Robe sur mesure"


def test_catalogue_list_is_sorted_and_filters_inactive_items(
    admin_client: TestClient,
    catalogue_session: Session,
) -> None:
    catalogue_session.add_all(
        [
            TypeVetement(nom="Zèbre", prix_base=10, delai_jours=1, actif=True),
            TypeVetement(nom="Boubou", prix_base=20, delai_jours=2, actif=False),
            TypeVetement(nom="Chemise", prix_base=30, delai_jours=3, actif=True),
        ]
    )
    catalogue_session.commit()

    active = admin_client.get("/api/v1/catalogue")
    all_items = admin_client.get("/api/v1/catalogue?actifs_seulement=false")

    assert active.status_code == 200
    assert [item["nom"] for item in active.json()] == ["Chemise", "Zèbre"]
    assert [item["nom"] for item in all_items.json()] == [
        "Boubou",
        "Chemise",
        "Zèbre",
    ]


def test_catalogue_conflicts_not_found_and_modification(
    admin_client: TestClient,
    catalogue_session: Session,
) -> None:
    existing = TypeVetement(
        nom="Robe",
        description="Initiale",
        prix_base=30000,
        delai_jours=7,
        actif=True,
    )
    duplicate = TypeVetement(
        nom="Chemise",
        prix_base=15000,
        delai_jours=5,
        actif=True,
    )
    catalogue_session.add_all([existing, duplicate])
    catalogue_session.commit()
    catalogue_session.refresh(existing)

    conflict = admin_client.post(
        "/api/v1/catalogue",
        json={"nom": "Robe", "prix_base": 1, "delai_jours": 1},
    )
    duplicate_name = admin_client.patch(
        f"/api/v1/catalogue/{existing.id}", json={"nom": "Chemise"}
    )
    missing = admin_client.get("/api/v1/catalogue/9999")
    update = admin_client.patch(
        f"/api/v1/catalogue/{existing.id}",
        json={"description": None, "prix_base": 35000, "actif": False},
    )

    assert conflict.status_code == 409
    assert duplicate_name.status_code == 409
    assert missing.status_code == 404
    assert update.status_code == 200
    assert update.json()["description"] is None
    assert update.json()["prix_base"] == 35000
    assert update.json()["actif"] is False


def test_catalogue_reads_require_auth_and_writes_require_admin(
    admin_client: TestClient,
    monkeypatch,
) -> None:
    tailor = Utilisateur(
        id=99,
        email="tailleur@example.com",
        nom_complet="Tailleur",
        mot_de_passe_hash="unused",
        role=Role.tailleur,
        actif=True,
    )
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: tailor)

    read = admin_client.get("/api/v1/catalogue")
    create = admin_client.post(
        "/api/v1/catalogue",
        json={"nom": "Pantalon", "prix_base": 12000, "delai_jours": 4},
    )

    assert read.status_code == 200
    assert create.status_code == 403
