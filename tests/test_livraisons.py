from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies import get_current_user
from app.main import app
from app.models import Client, Commande, HistoriqueStatut, Livraison, TypeVetement, Utilisateur
from app.models.enums import Genre, Role, StatutCommande


@pytest.fixture
def livraison_context() -> Iterator[tuple[TestClient, Session, dict[str, object]]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)

    accueil = Utilisateur(
        email="accueil-livraison@example.com",
        nom_complet="Accueil",
        mot_de_passe_hash="unused",
        role=Role.accueil,
        actif=True,
    )
    tailleur = Utilisateur(
        email="tailleur-livraison@example.com",
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
    session.add_all([accueil, tailleur, client_record, prestation])
    session.commit()
    for record in (accueil, tailleur, client_record, prestation):
        session.refresh(record)

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: accueil
    try:
        with TestClient(app) as test_client:
            yield test_client, session, {
                "accueil": accueil,
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


def set_status(
    session: Session,
    order_id: int,
    status: StatutCommande,
) -> None:
    order = session.get(Commande, order_id)
    assert order is not None
    order.statut = status
    session.commit()


def test_plan_and_reschedule_delivery_without_creating_duplicates(
    livraison_context,
) -> None:
    test_client, session, records = livraison_context
    order = create_order(test_client, records)

    planned = test_client.put(
        f"/api/v1/commandes/{order['id']}/livraison",
        json={
            "mode": "domicile",
            "adresse": "  10 rue des Fleurs  ",
            "livreur": "Awa",
            "notes": "Appeler avant d'arriver",
        },
    )
    assert planned.status_code == 200
    delivery = planned.json()
    assert delivery["commande_id"] == order["id"]
    assert delivery["mode"] == "domicile"
    assert delivery["adresse"] == "10 rue des Fleurs"
    assert delivery["date_prevue"] == order["date_livraison_prevue"]
    assert delivery["statut"] == "planifiee"

    rescheduled = test_client.put(
        f"/api/v1/commandes/{order['id']}/livraison",
        json={
            "mode": "retrait_atelier",
            "date_prevue": (date.today() + timedelta(days=2)).isoformat(),
        },
    )
    assert rescheduled.status_code == 200
    assert rescheduled.json()["id"] == delivery["id"]
    assert rescheduled.json()["adresse"] is None
    assert rescheduled.json()["date_prevue"] == (
        date.today() + timedelta(days=2)
    ).isoformat()
    assert len(
        session.scalars(
            select(Livraison).where(Livraison.commande_id == order["id"])
        ).all()
    ) == 1


def test_plan_delivery_validates_address_date_command_and_role(
    livraison_context,
    monkeypatch,
) -> None:
    test_client, session, records = livraison_context
    order = create_order(test_client, records)

    no_address = test_client.put(
        f"/api/v1/commandes/{order['id']}/livraison",
        json={"mode": "domicile", "adresse": "  "},
    )
    past_date = test_client.put(
        f"/api/v1/commandes/{order['id']}/livraison",
        json={"mode": "retrait_atelier", "date_prevue": "2020-01-01"},
    )
    missing_order = test_client.put(
        "/api/v1/commandes/9999/livraison",
        json={"mode": "retrait_atelier"},
    )
    assert no_address.status_code == 422
    assert "exige une adresse" in no_address.json()["detail"]
    assert past_date.status_code == 422
    assert missing_order.status_code == 404

    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: records["tailleur"],
    )
    forbidden = test_client.put(
        f"/api/v1/commandes/{order['id']}/livraison",
        json={"mode": "retrait_atelier"},
    )
    assert forbidden.status_code == 403

    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: records["accueil"],
    )
    set_status(session, order["id"], StatutCommande.annulee)
    final_order = test_client.put(
        f"/api/v1/commandes/{order['id']}/livraison",
        json={"mode": "retrait_atelier"},
    )
    assert final_order.status_code == 409


def test_read_delivery_and_tour_filters(livraison_context) -> None:
    test_client, _, records = livraison_context
    order = create_order(test_client, records)
    order_without_delivery = create_order(test_client, records)
    planned = test_client.put(
        f"/api/v1/commandes/{order['id']}/livraison",
        json={
            "mode": "retrait_atelier",
            "date_prevue": date.today().isoformat(),
        },
    )
    assert planned.status_code == 200

    detail = test_client.get(f"/api/v1/commandes/{order['id']}/livraison")
    missing_delivery = test_client.get("/api/v1/commandes/9999/livraison")
    no_delivery = test_client.get(
        f"/api/v1/commandes/{order_without_delivery['id']}/livraison"
    )
    tour = test_client.get("/api/v1/livraisons")
    filtered = test_client.get(
        f"/api/v1/livraisons?statut=planifiee&date_min={date.today().isoformat()}"
    )
    no_match = test_client.get(
        "/api/v1/livraisons?statut=livree"
    )

    assert detail.status_code == 200
    assert detail.json()["id"] == planned.json()["id"]
    assert missing_delivery.status_code == 404
    assert no_delivery.status_code == 404
    assert tour.status_code == 200 and len(tour.json()) == 1
    assert filtered.status_code == 200 and len(filtered.json()) == 1
    assert no_match.status_code == 200 and no_match.json() == []


def test_confirmation_requires_completed_order_and_balance_authorization(
    livraison_context,
) -> None:
    test_client, session, records = livraison_context
    order = create_order(test_client, records)

    not_completed = test_client.post(
        f"/api/v1/commandes/{order['id']}/livraison/confirmer",
        json={},
    )
    assert not_completed.status_code == 409
    assert "statut terminee" in not_completed.json()["detail"]

    set_status(session, order["id"], StatutCommande.terminee)
    unpaid = test_client.post(
        f"/api/v1/commandes/{order['id']}/livraison/confirmer",
        json={},
    )
    assert unpaid.status_code == 409
    assert "reste 70000 FCFA à payer" in unpaid.json()["detail"]

    confirmed = test_client.post(
        f"/api/v1/commandes/{order['id']}/livraison/confirmer",
        json={"autoriser_solde_impaye": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["mode"] == "retrait_atelier"
    assert confirmed.json()["date_prevue"] == date.today().isoformat()
    assert confirmed.json()["date_effective"] == date.today().isoformat()
    assert confirmed.json()["statut"] == "livree"

    order_model = session.get(Commande, order["id"])
    assert order_model is not None
    session.refresh(order_model)
    order_detail = test_client.get(f"/api/v1/commandes/{order['id']}")
    assert order_detail.json()["statut"] == "livree"
    assert order_detail.json()["date_livraison_reelle"] == date.today().isoformat()
    history = test_client.get(f"/api/v1/commandes/{order['id']}/historique")
    assert history.json()[-1]["ancien_statut"] == "terminee"
    assert history.json()[-1]["nouveau_statut"] == "livree"
    assert "solde impayé de 70000 FCFA" in history.json()[-1]["commentaire"]


def test_confirmation_with_zero_balance_and_planned_delivery(
    livraison_context,
) -> None:
    test_client, session, records = livraison_context
    order = create_order(test_client, records)
    planned = test_client.put(
        f"/api/v1/commandes/{order['id']}/livraison",
        json={"mode": "domicile", "adresse": "Dakar"},
    )
    assert planned.status_code == 200

    order_model = session.get(Commande, order["id"])
    assert order_model is not None
    order_model.statut = StatutCommande.terminee
    order_model.montant_paye = order_model.montant_total
    session.commit()

    confirmed = test_client.post(
        f"/api/v1/commandes/{order['id']}/livraison/confirmer",
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["id"] == planned.json()["id"]
    assert confirmed.json()["mode"] == "domicile"
    assert confirmed.json()["adresse"] == "Dakar"
    assert confirmed.json()["statut"] == "livree"


def test_delivery_writes_are_reserved_to_accueil(livraison_context, monkeypatch) -> None:
    test_client, _, records = livraison_context
    order = create_order(test_client, records)
    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: records["tailleur"],
    )

    plan = test_client.put(
        f"/api/v1/commandes/{order['id']}/livraison",
        json={"mode": "retrait_atelier"},
    )
    confirm = test_client.post(
        f"/api/v1/commandes/{order['id']}/livraison/confirmer",
        json={"autoriser_solde_impaye": True},
    )

    assert plan.status_code == 403
    assert confirm.status_code == 403
