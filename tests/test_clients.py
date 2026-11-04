from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies import get_current_user
from app.main import app
from app.models import Client, Commande, Mesure, Utilisateur
from app.models.enums import Genre, Role, StatutCommande


@pytest.fixture
def client_db() -> Iterator[Session]:
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
def client_api(client_db: Session) -> Iterator[TestClient]:
    admin = Utilisateur(
        email="admin@example.com",
        nom_complet="Admin",
        mot_de_passe_hash="unused",
        role=Role.admin,
        actif=True,
    )
    client_db.add(admin)
    client_db.commit()
    client_db.refresh(admin)
    app.dependency_overrides[get_db] = lambda: client_db
    app.dependency_overrides[get_current_user] = lambda: admin
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_client(
    db: Session,
    *,
    nom: str,
    prenom: str,
    telephone: str,
    genre: Genre = Genre.femme,
) -> Client:
    client = Client(
        nom=nom,
        prenom=prenom,
        telephone=telephone,
        genre=genre,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def create_order(
    db: Session,
    client: Client,
    user: Utilisateur,
    *,
    order_number: str,
    order_date: date,
    total: int,
    paid: int,
    status: StatutCommande = StatutCommande.en_attente,
) -> Commande:
    order = Commande(
        numero=order_number,
        client_id=client.id,
        statut=status,
        date_commande=order_date,
        date_livraison_prevue=order_date,
        montant_total=total,
        montant_paye=paid,
        cree_par_id=user.id,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def test_client_creation_normalizes_phone_and_rejects_duplicate(
    client_api: TestClient,
) -> None:
    payload = {
        "nom": "Diallo",
        "prenom": "Awa",
        "telephone": "(+221) 77-123.45 67",
        "genre": "femme",
    }

    created = client_api.post("/api/v1/clients", json=payload)
    duplicate = client_api.post(
        "/api/v1/clients",
        json={**payload, "telephone": "+221771234567"},
    )

    assert created.status_code == 201
    assert created.json()["telephone"] == "+221771234567"
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": "Un client existe déjà avec ce numéro de téléphone"
    }


def test_client_list_filters_searches_and_paginates(
    client_api: TestClient,
    client_db: Session,
) -> None:
    create_client(
        client_db,
        nom="Ba",
        prenom="Moussa",
        telephone="771111111",
        genre=Genre.homme,
    )
    create_client(
        client_db,
        nom="Diallo",
        prenom="Awa",
        telephone="772222222",
        genre=Genre.femme,
    )
    create_client(
        client_db,
        nom="Diallo",
        prenom="Binta",
        telephone="773333333",
        genre=Genre.femme,
    )

    page = client_api.get("/api/v1/clients?genre=femme&limit=1&offset=1")
    search_name = client_api.get("/api/v1/clients?q=awa")
    search_phone = client_api.get("/api/v1/clients?q=77.222")

    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert page.json()["limit"] == 1
    assert page.json()["offset"] == 1
    assert page.json()["items"][0]["prenom"] == "Binta"
    assert search_name.json()["total"] == 1
    assert search_name.json()["items"][0]["prenom"] == "Awa"
    assert search_phone.json()["total"] == 1
    assert search_phone.json()["items"][0]["telephone"] == "772222222"


def test_client_read_update_and_phone_conflicts(
    client_api: TestClient,
    client_db: Session,
) -> None:
    first = create_client(
        client_db, nom="Ba", prenom="Awa", telephone="771111111"
    )
    second = create_client(
        client_db, nom="Diallo", prenom="Moussa", telephone="772222222"
    )

    read = client_api.get(f"/api/v1/clients/{first.id}")
    updated = client_api.patch(
        f"/api/v1/clients/{first.id}",
        json={"telephone": "(77) 111-11-11", "notes": "  Client fidèle  "},
    )
    duplicate = client_api.patch(
        f"/api/v1/clients/{first.id}",
        json={"telephone": second.telephone},
    )
    missing = client_api.get("/api/v1/clients/9999")

    assert read.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["telephone"] == "771111111"
    assert updated.json()["notes"] == "Client fidèle"
    assert duplicate.status_code == 409
    assert missing.status_code == 404


def test_client_orders_and_summary_exclude_cancelled_orders(
    client_api: TestClient,
    client_db: Session,
) -> None:
    user = client_db.scalar(
        select(Utilisateur).where(Utilisateur.email == "admin@example.com")
    )
    assert user is not None
    customer = create_client(
        client_db, nom="Sow", prenom="Fatou", telephone="771234567"
    )
    create_order(
        client_db,
        customer,
        user,
        order_number="CMD-0001",
        order_date=date(2026, 1, 1),
        total=10000,
        paid=4000,
    )
    create_order(
        client_db,
        customer,
        user,
        order_number="CMD-0002",
        order_date=date(2026, 2, 1),
        total=20000,
        paid=5000,
    )
    create_order(
        client_db,
        customer,
        user,
        order_number="CMD-0003",
        order_date=date(2026, 3, 1),
        total=90000,
        paid=90000,
        status=StatutCommande.annulee,
    )

    orders = client_api.get(
        f"/api/v1/clients/{customer.id}/commandes?limit=1&offset=0"
    )
    summary = client_api.get(f"/api/v1/clients/{customer.id}/resume")

    assert orders.status_code == 200
    assert orders.json()["total"] == 3
    assert orders.json()["items"][0]["numero"] == "CMD-0003"
    assert orders.json()["items"][0]["solde"] == 0
    assert summary.status_code == 200
    assert summary.json() == {
        "nb_commandes": 2,
        "chiffre_affaires": 30000,
        "total_paye": 9000,
        "solde_du": 21000,
        "derniere_commande": "2026-02-01",
        "a_des_mesures": False,
    }

    measurement = Mesure(
        client_id=customer.id,
        prise_par_id=user.id,
        taille_cm=165.0,
    )
    client_db.add(measurement)
    client_db.commit()
    summary = client_api.get(f"/api/v1/clients/{customer.id}/resume")
    assert summary.json()["a_des_mesures"] is True


def test_client_delete_requires_admin_and_blocks_existing_orders(
    client_api: TestClient,
    client_db: Session,
    monkeypatch,
) -> None:
    user = client_db.scalar(
        select(Utilisateur).where(Utilisateur.email == "admin@example.com")
    )
    assert user is not None
    customer = create_client(
        client_db, nom="Ndiaye", prenom="Ali", telephone="771234567"
    )
    order = create_order(
        client_db,
        customer,
        user,
        order_number="CMD-0001",
        order_date=date(2026, 1, 1),
        total=1000,
        paid=0,
    )
    blocked = client_api.delete(f"/api/v1/clients/{customer.id}")
    client_db.delete(order)
    client_db.commit()
    removed = client_api.delete(f"/api/v1/clients/{customer.id}")

    assert blocked.status_code == 409
    assert removed.status_code == 204
    assert client_db.get(Client, customer.id) is None

    tailor = Utilisateur(
        id=999,
        email="tailleur@example.com",
        nom_complet="Tailleur",
        mot_de_passe_hash="unused",
        role=Role.tailleur,
        actif=True,
    )
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: tailor)
    forbidden = client_api.delete("/api/v1/clients/9999")
    assert forbidden.status_code == 403


def test_deleting_client_cascades_measurements(
    client_api: TestClient,
    client_db: Session,
) -> None:
    user = client_db.scalar(
        select(Utilisateur).where(Utilisateur.email == "admin@example.com")
    )
    assert user is not None
    customer = create_client(
        client_db, nom="Fall", prenom="Mariam", telephone="771112233"
    )
    measurement = Mesure(
        client_id=customer.id,
        prise_par_id=user.id,
        taille_cm=160.0,
    )
    client_db.add(measurement)
    client_db.commit()
    measurement_id = measurement.id

    response = client_api.delete(f"/api/v1/clients/{customer.id}")

    assert response.status_code == 204
    assert client_db.get(Mesure, measurement_id) is None
