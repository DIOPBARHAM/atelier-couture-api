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
from app.models import Client, Commande, Mesure, TypeVetement, Utilisateur
from app.models.enums import Genre, Role


@pytest.fixture
def mesure_context() -> Iterator[tuple[TestClient, Session, dict[str, Utilisateur]]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    admin = Utilisateur(
        email="admin@example.com",
        nom_complet="Admin",
        mot_de_passe_hash="unused",
        role=Role.admin,
        actif=True,
    )
    tailor = Utilisateur(
        email="tailleur@example.com",
        nom_complet="Tailleur",
        mot_de_passe_hash="unused",
        role=Role.tailleur,
        actif=True,
    )
    accueil = Utilisateur(
        email="accueil@example.com",
        nom_complet="Accueil",
        mot_de_passe_hash="unused",
        role=Role.accueil,
        actif=True,
    )
    customer = Client(
        nom="Diop",
        prenom="Fatou",
        telephone="771234567",
        genre=Genre.femme,
    )
    session.add_all([admin, tailor, accueil, customer])
    session.commit()
    session.refresh(admin)
    session.refresh(tailor)
    session.refresh(accueil)
    session.refresh(customer)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: tailor

    try:
        with TestClient(app) as client:
            yield client, session, {
                "admin": admin,
                "tailleur": tailor,
                "accueil": accueil,
                "client": customer,
            }
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


def test_tailor_can_create_measure_and_it_defaults_to_today(mesure_context) -> None:
    client, _, records = mesure_context

    response = client.post(
        f"/api/v1/clients/{records['client'].id}/mesures",
        json={"taille_cm": 165, "tour_poitrine": 92},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["client_id"] == records["client"].id
    assert body["prise_par_id"] == records["tailleur"].id
    assert body["date_prise"] == date.today().isoformat()
    assert body["taille_cm"] == 165


def test_accueil_cannot_write_measure_but_can_read_history(
    mesure_context,
    monkeypatch,
) -> None:
    client, session, records = mesure_context
    measurement = Mesure(
        client_id=records["client"].id,
        prise_par_id=records["tailleur"].id,
        date_prise=date.today(),
        taille_cm=165,
    )
    session.add(measurement)
    session.commit()
    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: records["accueil"],
    )

    write = client.post(
        f"/api/v1/clients/{records['client'].id}/mesures",
        json={"taille_cm": 170},
    )
    read = client.get(f"/api/v1/clients/{records['client'].id}/mesures")

    assert write.status_code == 403
    assert read.status_code == 200
    assert len(read.json()) == 1


def test_measure_history_is_newest_first_and_last_endpoint_matches(
    mesure_context,
) -> None:
    client, session, records = mesure_context
    older = Mesure(
        client_id=records["client"].id,
        prise_par_id=records["tailleur"].id,
        date_prise=date.today() - timedelta(days=2),
        taille_cm=160,
    )
    newer_first = Mesure(
        client_id=records["client"].id,
        prise_par_id=records["tailleur"].id,
        date_prise=date.today(),
        taille_cm=170,
    )
    newer_second = Mesure(
        client_id=records["client"].id,
        prise_par_id=records["tailleur"].id,
        date_prise=date.today(),
        taille_cm=175,
    )
    session.add_all([older, newer_first, newer_second])
    session.commit()

    history = client.get(f"/api/v1/clients/{records['client'].id}/mesures")
    latest = client.get(
        f"/api/v1/clients/{records['client'].id}/mesures/derniere"
    )

    assert history.status_code == 200
    assert [item["taille_cm"] for item in history.json()] == [175, 170, 160]
    assert latest.status_code == 200
    assert latest.json()["id"] == history.json()[0]["id"]


def test_measure_endpoints_return_not_found_for_missing_records(
    mesure_context,
) -> None:
    client, _, records = mesure_context

    missing_client_history = client.get("/api/v1/clients/9999/mesures")
    no_measurements = client.get(
        f"/api/v1/clients/{records['client'].id}/mesures/derniere"
    )
    missing_measurement = client.get("/api/v1/mesures/9999")

    assert missing_client_history.status_code == 404
    assert no_measurements.status_code == 404
    assert no_measurements.json() == {
        "detail": "Aucune mesure enregistrée pour ce client"
    }
    assert missing_measurement.status_code == 404


def test_measure_can_be_read_corrected_and_cannot_be_left_empty(
    mesure_context,
) -> None:
    client, session, records = mesure_context
    measurement = Mesure(
        client_id=records["client"].id,
        prise_par_id=records["tailleur"].id,
        date_prise=date.today(),
        taille_cm=165,
        tour_cou=35,
    )
    session.add(measurement)
    session.commit()
    session.refresh(measurement)

    read = client.get(f"/api/v1/mesures/{measurement.id}")
    corrected = client.patch(
        f"/api/v1/mesures/{measurement.id}",
        json={"taille_cm": None, "notes": "Correction"},
    )
    empty = client.patch(
        f"/api/v1/mesures/{measurement.id}",
        json={"tour_cou": None},
    )
    clear_date = client.patch(
        f"/api/v1/mesures/{measurement.id}",
        json={"date_prise": None},
    )

    assert read.status_code == 200
    assert corrected.status_code == 200
    assert corrected.json()["taille_cm"] is None
    assert corrected.json()["tour_cou"] == 35
    assert empty.status_code == 422
    assert "au moins une mesure" in empty.json()["detail"].lower()
    assert clear_date.status_code == 422


def test_measure_write_and_delete_are_restricted_to_tailors(
    mesure_context,
    monkeypatch,
) -> None:
    client, session, records = mesure_context
    measurement = Mesure(
        client_id=records["client"].id,
        prise_par_id=records["tailleur"].id,
        date_prise=date.today(),
        taille_cm=165,
    )
    session.add(measurement)
    session.commit()
    session.refresh(measurement)
    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: records["admin"],
    )

    write = client.post(
        f"/api/v1/clients/{records['client'].id}/mesures",
        json={"taille_cm": 170},
    )
    delete = client.delete(f"/api/v1/mesures/{measurement.id}")

    assert write.status_code == 403
    assert delete.status_code == 403


def test_measure_delete_is_blocked_when_linked_to_order(mesure_context) -> None:
    client, session, records = mesure_context
    garment = TypeVetement(
        nom="Robe",
        prix_base=10000,
        delai_jours=5,
        actif=True,
    )
    session.add(garment)
    measurement = Mesure(
        client_id=records["client"].id,
        prise_par_id=records["tailleur"].id,
        date_prise=date.today(),
        taille_cm=165,
    )
    session.add(measurement)
    session.commit()
    session.refresh(garment)
    session.refresh(measurement)
    order = Commande(
        numero="CMD-MES-1",
        client_id=records["client"].id,
        mesure_id=measurement.id,
        date_commande=date.today(),
        date_livraison_prevue=date.today(),
        cree_par_id=records["admin"].id,
    )
    session.add(order)
    session.commit()

    response = client.delete(f"/api/v1/mesures/{measurement.id}")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Suppression impossible : ces mesures sont rattachées à une commande"
    }


def test_tailor_can_delete_unlinked_measure(mesure_context) -> None:
    client, session, records = mesure_context
    measurement = Mesure(
        client_id=records["client"].id,
        prise_par_id=records["tailleur"].id,
        date_prise=date.today(),
        taille_cm=165,
    )
    session.add(measurement)
    session.commit()
    session.refresh(measurement)

    response = client.delete(f"/api/v1/mesures/{measurement.id}")

    assert response.status_code == 204
    assert session.get(Mesure, measurement.id) is None
