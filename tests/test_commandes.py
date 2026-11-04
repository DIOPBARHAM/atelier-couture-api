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
from app.models import (
    Client,
    Commande,
    HistoriqueStatut,
    LigneCommande,
    Mesure,
    Paiement,
    TypeVetement,
    Utilisateur,
)
from app.models.enums import Genre, ModePaiement, Role, StatutCommande


@pytest.fixture
def commande_context() -> Iterator[tuple[TestClient, Session, dict[str, object]]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)

    accueil = Utilisateur(
        email="accueil@example.com",
        nom_complet="Accueil",
        mot_de_passe_hash="unused",
        role=Role.accueil,
        actif=True,
    )
    tailor = Utilisateur(
        email="tailleur@example.com",
        nom_complet="Tailleur",
        mot_de_passe_hash="unused",
        role=Role.tailleur,
        actif=True,
    )
    customer = Client(
        nom="Diop",
        prenom="Fatou",
        telephone="771234567",
        genre=Genre.femme,
    )
    other_customer = Client(
        nom="Fall",
        prenom="Aminata",
        telephone="772223344",
        genre=Genre.femme,
    )
    dress = TypeVetement(
        nom="Robe",
        prix_base=30000,
        delai_jours=7,
        actif=True,
    )
    shirt = TypeVetement(
        nom="Chemise",
        prix_base=15000,
        delai_jours=5,
        actif=True,
    )
    inactive = TypeVetement(
        nom="Veste inactive",
        prix_base=50000,
        delai_jours=10,
        actif=False,
    )
    session.add_all(
        [accueil, tailor, customer, other_customer, dress, shirt, inactive]
    )
    session.commit()
    for record in (accueil, tailor, customer, other_customer, dress, shirt, inactive):
        session.refresh(record)

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: accueil
    try:
        with TestClient(app) as client:
            yield client, session, {
                "accueil": accueil,
                "tailleur": tailor,
                "client": customer,
                "other_client": other_customer,
                "robe": dress,
                "chemise": shirt,
                "inactive": inactive,
            }
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


def create_order(
    client: TestClient,
    records: dict[str, object],
    *,
    lines: list[dict[str, object]] | None = None,
    **overrides: object,
):
    payload: dict[str, object] = {
        "client_id": records["client"].id,
        "lignes": lines
        or [
            {
                "type_vetement_id": records["robe"].id,
                "quantite": 2,
            }
        ],
    }
    payload.update(overrides)
    return client.post("/api/v1/commandes", json=payload)


def test_create_order_calculates_number_totals_dates_and_history(
    commande_context,
) -> None:
    client, session, records = commande_context
    measurement = Mesure(
        client_id=records["client"].id,
        prise_par_id=records["tailleur"].id,
        date_prise=date.today(),
        taille_cm=165,
    )
    session.add(measurement)
    session.commit()
    session.refresh(measurement)

    response = create_order(
        client,
        records,
        lines=[
            {
                "type_vetement_id": records["robe"].id,
                "quantite": 2,
            },
            {
                "type_vetement_id": records["chemise"].id,
                "description": "Chemise brodée",
                "quantite": 1,
                "prix_unitaire": 18000,
            },
        ],
        remise=5000,
    )

    assert response.status_code == 201
    order = response.json()
    assert order["numero"] == f"CMD-{date.today().year}-00001"
    assert order["client_id"] == records["client"].id
    assert order["mesure_id"] == measurement.id
    assert order["statut"] == "en_attente"
    assert order["date_commande"] == date.today().isoformat()
    assert order["date_livraison_prevue"] == (
        date.today() + timedelta(days=7)
    ).isoformat()
    assert order["montant_total"] == 73000
    assert order["montant_paye"] == 0
    assert order["solde"] == 73000
    assert len(order["lignes"]) == 2
    assert order["lignes"][0]["sous_total"] == 60000
    assert order["lignes"][1]["sous_total"] == 18000
    assert order["paiements"] == []
    assert order["livraison"] is None

    history = session.scalars(
        select(HistoriqueStatut).where(
            HistoriqueStatut.commande_id == order["id"]
        )
    ).all()
    assert len(history) == 1
    assert history[0].ancien_statut is None
    assert history[0].nouveau_statut is StatutCommande.en_attente
    assert history[0].utilisateur_id == records["accueil"].id


def test_create_order_rejects_invalid_client_measure_service_discount_and_dates(
    commande_context,
) -> None:
    client, session, records = commande_context
    other_measure = Mesure(
        client_id=records["other_client"].id,
        prise_par_id=records["tailleur"].id,
        date_prise=date.today(),
        taille_cm=170,
    )
    session.add(other_measure)
    session.commit()
    session.refresh(other_measure)

    missing_client = create_order(client, records, client_id=9999)
    wrong_measure = create_order(
        client, records, mesure_id=other_measure.id
    )
    inactive_service = create_order(
        client,
        records,
        lines=[
            {
                "type_vetement_id": records["inactive"].id,
                "quantite": 1,
            }
        ],
    )
    unknown_service = create_order(
        client,
        records,
        lines=[{"type_vetement_id": 9999, "quantite": 1}],
    )
    excess_discount = create_order(client, records, remise=60001)
    invalid_dates = create_order(
        client,
        records,
        date_commande="2026-04-10",
        date_livraison_prevue="2026-04-09",
    )
    empty_lines = client.post(
        "/api/v1/commandes",
        json={"client_id": records["client"].id, "lignes": []},
    )

    assert missing_client.status_code == 404
    assert wrong_measure.status_code == 422
    assert inactive_service.status_code == 422
    assert unknown_service.status_code == 404
    assert excess_discount.status_code == 422
    assert invalid_dates.status_code == 422
    assert empty_lines.status_code == 422
    assert "élément" in empty_lines.json()["detail"]


def test_explicit_dates_measure_validation_and_yearly_numbering(
    commande_context,
) -> None:
    client, session, records = commande_context
    correct_measure = Mesure(
        client_id=records["client"].id,
        prise_par_id=records["tailleur"].id,
        date_prise=date(2026, 1, 1),
        taille_cm=160,
    )
    session.add(correct_measure)
    session.commit()
    session.refresh(correct_measure)

    first = create_order(
        client,
        records,
        date_commande="2025-12-30",
        date_livraison_prevue="2026-01-20",
        mesure_id=correct_measure.id,
    )
    second = create_order(
        client,
        records,
        date_commande="2025-12-31",
    )

    assert first.status_code == 201
    assert first.json()["numero"] == "CMD-2025-00001"
    assert first.json()["date_livraison_prevue"] == "2026-01-20"
    assert first.json()["mesure_id"] == correct_measure.id
    assert second.status_code == 201
    assert second.json()["numero"] == "CMD-2025-00002"


def test_read_and_filter_orders_with_pagination_and_overdue_status(
    commande_context,
) -> None:
    client, _, records = commande_context
    yesterday = date.today() - timedelta(days=1)
    overdue = create_order(
        client,
        records,
        date_commande=yesterday.isoformat(),
        date_livraison_prevue=yesterday.isoformat(),
    )
    due_today = create_order(
        client,
        records,
        date_livraison_prevue=date.today().isoformat(),
    )
    assert overdue.status_code == due_today.status_code == 201

    read = client.get(f"/api/v1/commandes/{overdue.json()['id']}")
    overdue_filter = client.get("/api/v1/commandes?en_retard=true")
    not_overdue_filter = client.get("/api/v1/commandes?en_retard=false")
    status_filter = client.get("/api/v1/commandes?statut=en_attente&limit=1")
    number_filter = client.get(
        f"/api/v1/commandes?numero={overdue.json()['numero'][-5:]}"
    )
    missing = client.get("/api/v1/commandes/9999")

    assert read.status_code == 200
    assert read.json()["en_retard"] is True
    assert overdue_filter.status_code == 200
    assert overdue_filter.json()["total"] == 1
    assert overdue_filter.json()["items"][0]["id"] == overdue.json()["id"]
    assert not_overdue_filter.json()["total"] == 1
    assert status_filter.json()["total"] == 2
    assert len(status_filter.json()["items"]) == 1
    assert number_filter.json()["total"] == 1
    assert missing.status_code == 404


def test_modify_order_recalculates_amount_and_checks_paid_amount(
    commande_context,
) -> None:
    client, session, records = commande_context
    created = create_order(client, records)
    order_id = created.json()["id"]
    order = session.get(Commande, order_id)
    assert order is not None
    order.paiements.append(
        Paiement(
            montant=10000,
            mode=ModePaiement.especes,
            date_paiement=date.today(),
            enregistre_par_id=records["accueil"].id,
        )
    )
    session.commit()

    updated = client.patch(
        f"/api/v1/commandes/{order_id}",
        json={"remise": 5000, "notes": "Retrait en atelier"},
    )
    over_discount = client.patch(
        f"/api/v1/commandes/{order_id}",
        json={"remise": 55000},
    )
    past_delivery = client.patch(
        f"/api/v1/commandes/{order_id}",
        json={"date_livraison_prevue": "2020-01-01"},
    )

    assert updated.status_code == 200
    assert updated.json()["montant_total"] == 55000
    assert updated.json()["montant_paye"] == 10000
    assert updated.json()["solde"] == 45000
    assert updated.json()["notes"] == "Retrait en atelier"
    assert len(updated.json()["paiements"]) == 1
    assert over_discount.status_code == 409
    assert past_delivery.status_code == 422

    order.paiements[0].montant = 57000
    session.commit()
    session.refresh(order)
    below_paid = client.patch(
        f"/api/v1/commandes/{order_id}",
        json={"remise": 5000},
    )
    assert below_paid.status_code == 409


def test_line_management_recalculates_and_enforces_minimum_and_pending_status(
    commande_context,
) -> None:
    client, _, records = commande_context
    created = create_order(client, records)
    order_id = created.json()["id"]
    initial_line_id = created.json()["lignes"][0]["id"]

    added = client.post(
        f"/api/v1/commandes/{order_id}/lignes",
        json={
            "type_vetement_id": records["chemise"].id,
            "quantite": 2,
        },
    )
    new_line_id = added.json()["lignes"][1]["id"]
    deleted = client.delete(
        f"/api/v1/commandes/{order_id}/lignes/{initial_line_id}"
    )
    last_line = client.delete(
        f"/api/v1/commandes/{order_id}/lignes/{new_line_id}"
    )

    assert added.status_code == 201
    assert added.json()["montant_total"] == 90000
    assert added.json()["lignes"][1]["sous_total"] == 30000
    assert deleted.status_code == 200
    assert deleted.json()["montant_total"] == 30000
    assert last_line.status_code == 409

    order_id = added.json()["id"]
    order = _.get(Commande, order_id)
    assert order is not None
    order.statut = StatutCommande.en_coupe
    _.commit()
    blocked_add = client.post(
        f"/api/v1/commandes/{order_id}/lignes",
        json={
            "type_vetement_id": records["chemise"].id,
            "quantite": 1,
        },
    )
    blocked_delete = client.delete(
        f"/api/v1/commandes/{order_id}/lignes/{new_line_id}"
    )

    assert blocked_add.status_code == 409
    assert blocked_delete.status_code == 409


def test_line_deletion_cannot_exceed_discount_or_reduce_total_below_paid(
    commande_context,
) -> None:
    client, session, records = commande_context
    created = create_order(
        client,
        records,
        lines=[
            {"type_vetement_id": records["robe"].id, "quantite": 1},
            {"type_vetement_id": records["chemise"].id, "quantite": 1},
        ],
        remise=20000,
    )
    order_id = created.json()["id"]
    robe_line_id = created.json()["lignes"][0]["id"]
    order = session.get(Commande, order_id)
    assert order is not None
    order.paiements.append(
        Paiement(
            montant=26000,
            mode=ModePaiement.especes,
            enregistre_par_id=records["accueil"].id,
        )
    )
    session.commit()

    conflict_discount = client.delete(
        f"/api/v1/commandes/{order_id}/lignes/{robe_line_id}"
    )
    order.remise = 5000
    order.paiements[0].montant = 11000
    session.commit()
    conflict_paid = client.delete(
        f"/api/v1/commandes/{order_id}/lignes/{robe_line_id}"
    )

    assert conflict_discount.status_code == 409
    assert "remise" in conflict_discount.json()["detail"].lower()
    assert conflict_paid.status_code == 409
    assert "montant déjà payé" in conflict_paid.json()["detail"].lower()


def test_order_write_routes_require_accueil_and_reads_require_auth(
    commande_context,
    monkeypatch,
) -> None:
    client, _, records = commande_context
    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: records["tailleur"],
    )

    create = create_order(client, records)
    listing = client.get("/api/v1/commandes")

    assert create.status_code == 403
    assert listing.status_code == 200


def test_status_workflow_validates_transitions_and_exposes_history(
    commande_context,
) -> None:
    client, _, records = commande_context
    created = create_order(client, records)
    order_id = created.json()["id"]

    invalid = client.post(
        f"/api/v1/commandes/{order_id}/statut",
        json={"statut": "terminee"},
    )
    transition = client.post(
        f"/api/v1/commandes/{order_id}/statut",
        json={"statut": "en_coupe", "commentaire": "  coupe démarrée  "},
    )
    same_status = client.post(
        f"/api/v1/commandes/{order_id}/statut",
        json={"statut": "en_coupe"},
    )
    direct_delivery = client.post(
        f"/api/v1/commandes/{order_id}/statut",
        json={"statut": "livree"},
    )
    history = client.get(f"/api/v1/commandes/{order_id}/historique")
    missing_history = client.get("/api/v1/commandes/9999/historique")

    assert invalid.status_code == 409
    assert "Statuts possibles : annulee, en_coupe" in invalid.json()["detail"]
    assert transition.status_code == 200
    assert transition.json()["statut"] == "en_coupe"
    assert same_status.status_code == 409
    assert "déjà au statut en_coupe" in same_status.json()["detail"]
    assert direct_delivery.status_code == 409
    assert "confirmation de livraison" in direct_delivery.json()["detail"]
    assert history.status_code == 200
    assert len(history.json()) == 2
    assert history.json()[0]["ancien_statut"] is None
    assert history.json()[0]["nouveau_statut"] == "en_attente"
    assert history.json()[1]["ancien_statut"] == "en_attente"
    assert history.json()[1]["nouveau_statut"] == "en_coupe"
    assert history.json()[1]["commentaire"] == "coupe démarrée"
    assert history.json()[1]["utilisateur_id"] == records["accueil"].id
    assert missing_history.status_code == 404


def test_cancellation_requires_authorization_and_comment_when_paid(
    commande_context,
    monkeypatch,
) -> None:
    client, session, records = commande_context
    created = create_order(client, records)
    order_id = created.json()["id"]
    order = session.get(Commande, order_id)
    assert order is not None
    order.montant_paye = 10000
    session.commit()

    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: records["tailleur"],
    )
    forbidden = client.post(
        f"/api/v1/commandes/{order_id}/statut",
        json={"statut": "annulee", "commentaire": "Client remboursé"},
    )
    assert forbidden.status_code == 403

    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: records["accueil"],
    )
    missing_comment = client.post(
        f"/api/v1/commandes/{order_id}/statut",
        json={"statut": "annulee"},
    )
    blank_comment = client.post(
        f"/api/v1/commandes/{order_id}/statut",
        json={"statut": "annulee", "commentaire": "   "},
    )
    cancelled = client.post(
        f"/api/v1/commandes/{order_id}/statut",
        json={
            "statut": "annulee",
            "commentaire": "  Acompte remboursé au client  ",
        },
    )

    assert missing_comment.status_code == 422
    assert "exige un commentaire" in missing_comment.json()["detail"]
    assert blank_comment.status_code == 422
    assert cancelled.status_code == 200
    assert cancelled.json()["statut"] == "annulee"
    history = client.get(f"/api/v1/commandes/{order_id}/historique")
    assert history.json()[-1]["commentaire"] == "Acompte remboursé au client"
