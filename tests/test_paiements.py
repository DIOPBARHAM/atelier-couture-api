from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies import get_current_user
from app.main import app
from app.models import Client, Commande, Paiement, TypeVetement, Utilisateur
from app.models.enums import Genre, ModePaiement, Role, StatutCommande


@pytest.fixture
def paiement_context() -> Iterator[tuple[TestClient, Session, dict[str, object]]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)

    accueil = Utilisateur(
        email="accueil-paiement@example.com",
        nom_complet="Accueil",
        mot_de_passe_hash="unused",
        role=Role.accueil,
        actif=True,
    )
    admin = Utilisateur(
        email="admin-paiement@example.com",
        nom_complet="Admin",
        mot_de_passe_hash="unused",
        role=Role.admin,
        actif=True,
    )
    tailleur = Utilisateur(
        email="tailleur-paiement@example.com",
        nom_complet="Tailleur",
        mot_de_passe_hash="unused",
        role=Role.tailleur,
        actif=True,
    )
    client_record = Client(
        nom="Diop",
        prenom="Fatou",
        telephone="771234567",
        genre=Genre.femme,
    )
    prestation = TypeVetement(
        nom="Boubou",
        prix_base=35000,
        delai_jours=10,
        actif=True,
    )
    session.add_all([accueil, admin, tailleur, client_record, prestation])
    session.commit()
    for record in (accueil, admin, tailleur, client_record, prestation):
        session.refresh(record)

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: accueil
    try:
        with TestClient(app) as test_client:
            yield test_client, session, {
                "accueil": accueil,
                "admin": admin,
                "tailleur": tailleur,
                "client": client_record,
                "prestation": prestation,
            }
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


def create_order(test_client: TestClient, records: dict[str, object]) -> dict:
    response = test_client.post(
        "/api/v1/commandes",
        json={
            "client_id": records["client"].id,
            "lignes": [
                {
                    "type_vetement_id": records["prestation"].id,
                    "quantite": 2,
                }
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def test_register_payment_updates_order_balance_and_lists_payments(
    paiement_context,
) -> None:
    test_client, _, records = paiement_context
    order = create_order(test_client, records)

    response = test_client.post(
        f"/api/v1/commandes/{order['id']}/paiements",
        json={
            "montant": 20000,
            "mode": "wave",
            "reference": "TX-123",
        },
    )

    assert response.status_code == 201
    payment = response.json()
    assert payment["commande_id"] == order["id"]
    assert payment["montant"] == 20000
    assert payment["mode"] == "wave"
    assert payment["reference"] == "TX-123"
    assert payment["date_paiement"] == date.today().isoformat()
    assert payment["enregistre_par_id"] == records["accueil"].id

    detail = test_client.get(f"/api/v1/commandes/{order['id']}")
    assert detail.status_code == 200
    assert detail.json()["montant_paye"] == 20000
    assert detail.json()["solde"] == 50000
    assert len(detail.json()["paiements"]) == 1

    listed = test_client.get(f"/api/v1/commandes/{order['id']}/paiements")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [payment["id"]]


def test_register_payment_validates_order_status_amount_and_date(
    paiement_context,
    monkeypatch,
) -> None:
    test_client, session, records = paiement_context
    order = create_order(test_client, records)
    path = f"/api/v1/commandes/{order['id']}/paiements"

    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: records["tailleur"],
    )
    forbidden = test_client.post(
        path,
        json={"montant": 1000, "mode": "especes"},
    )
    assert forbidden.status_code == 403
    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: records["accueil"],
    )

    invalid_amount = test_client.post(
        path,
        json={"montant": 0, "mode": "especes"},
    )
    future_date = test_client.post(
        path,
        json={
            "montant": 1000,
            "mode": "especes",
            "date_paiement": (date.today() + timedelta(days=1)).isoformat(),
        },
    )
    oversized = test_client.post(
        path,
        json={"montant": 70001, "mode": "especes"},
    )
    missing_order = test_client.post(
        "/api/v1/commandes/9999/paiements",
        json={"montant": 1000, "mode": "especes"},
    )

    assert invalid_amount.status_code == 422
    assert future_date.status_code == 422
    assert "futur" in future_date.json()["detail"]
    assert oversized.status_code == 409
    assert "dépasse le solde restant" in oversized.json()["detail"]
    assert missing_order.status_code == 404

    order_model = session.get(Commande, order["id"])
    assert order_model is not None
    order_model.statut = StatutCommande.annulee
    session.commit()
    cancelled = test_client.post(
        path,
        json={"montant": 1000, "mode": "especes"},
    )
    assert cancelled.status_code == 409
    assert "commande annulée" in cancelled.json()["detail"]


def test_cancel_payment_is_admin_only_and_recalculates_paid_amount(
    paiement_context,
    monkeypatch,
) -> None:
    test_client, session, records = paiement_context
    order = create_order(test_client, records)
    payment_response = test_client.post(
        f"/api/v1/commandes/{order['id']}/paiements",
        json={"montant": 20000, "mode": "especes"},
    )
    assert payment_response.status_code == 201
    payment_id = payment_response.json()["id"]

    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: records["accueil"],
    )
    forbidden = test_client.delete(f"/api/v1/paiements/{payment_id}")
    assert forbidden.status_code == 403

    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: records["admin"],
    )
    deleted = test_client.delete(f"/api/v1/paiements/{payment_id}")
    missing = test_client.delete("/api/v1/paiements/9999")

    assert deleted.status_code == 204
    assert missing.status_code == 404
    order_model = session.get(Commande, order["id"])
    assert order_model is not None
    session.refresh(order_model)
    assert order_model.montant_paye == 0
    assert order_model.solde == 70000
    assert session.query(Paiement).filter_by(id=payment_id).count() == 0


def test_payment_listing_requires_existing_order(paiement_context) -> None:
    test_client, _, records = paiement_context

    missing_order = test_client.get("/api/v1/commandes/9999/paiements")
    assert missing_order.status_code == 404
