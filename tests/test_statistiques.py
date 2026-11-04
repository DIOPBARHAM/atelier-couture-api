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
from app.models import (
    Client,
    Commande,
    LigneCommande,
    Livraison,
    Paiement,
    TypeVetement,
    Utilisateur,
)
from app.models.enums import (
    Genre,
    ModeLivraison,
    ModePaiement,
    Role,
    StatutCommande,
    StatutLivraison,
)


@pytest.fixture
def statistiques_context() -> Iterator[tuple[TestClient, Session, dict[str, object]]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)

    admin = Utilisateur(
        email="admin-statistiques@example.com",
        nom_complet="Admin",
        mot_de_passe_hash="unused",
        role=Role.admin,
        actif=True,
    )
    accueil = Utilisateur(
        email="accueil-statistiques@example.com",
        nom_complet="Accueil",
        mot_de_passe_hash="unused",
        role=Role.accueil,
        actif=True,
    )
    client_a = Client(
        nom="Diop",
        prenom="Fatou",
        telephone="771111111",
        genre=Genre.femme,
    )
    client_b = Client(
        nom="Fall",
        prenom="Aminata",
        telephone="772222222",
        genre=Genre.femme,
    )
    client_annule = Client(
        nom="Ndiaye",
        prenom="Mame",
        telephone="773333333",
        genre=Genre.femme,
    )
    boubou = TypeVetement(
        nom="Boubou",
        prix_base=4000,
        delai_jours=10,
        actif=True,
    )
    chemise = TypeVetement(
        nom="Chemise",
        prix_base=1000,
        delai_jours=5,
        actif=True,
    )
    session.add_all(
        [admin, accueil, client_a, client_b, client_annule, boubou, chemise]
    )
    session.commit()
    for record in (
        admin,
        accueil,
        client_a,
        client_b,
        client_annule,
        boubou,
        chemise,
    ):
        session.refresh(record)

    today = date.today()
    order_a = Commande(
        numero="CMD-STAT-001",
        client_id=client_a.id,
        mesure_id=None,
        statut=StatutCommande.en_couture,
        date_commande=today,
        date_livraison_prevue=today - timedelta(days=1),
        date_livraison_reelle=None,
        remise=0,
        montant_total=8000,
        montant_paye=3000,
        notes=None,
        cree_par_id=accueil.id,
    )
    order_b1 = Commande(
        numero="CMD-STAT-002",
        client_id=client_b.id,
        mesure_id=None,
        statut=StatutCommande.en_attente,
        date_commande=today,
        date_livraison_prevue=today + timedelta(days=4),
        date_livraison_reelle=None,
        remise=0,
        montant_total=1000,
        montant_paye=0,
        notes=None,
        cree_par_id=accueil.id,
    )
    order_b2 = Commande(
        numero="CMD-STAT-003",
        client_id=client_b.id,
        mesure_id=None,
        statut=StatutCommande.terminee,
        date_commande=today,
        date_livraison_prevue=today,
        date_livraison_reelle=None,
        remise=0,
        montant_total=1000,
        montant_paye=0,
        notes=None,
        cree_par_id=accueil.id,
    )
    cancelled = Commande(
        numero="CMD-STAT-004",
        client_id=client_annule.id,
        mesure_id=None,
        statut=StatutCommande.annulee,
        date_commande=today,
        date_livraison_prevue=today - timedelta(days=2),
        date_livraison_reelle=None,
        remise=0,
        montant_total=5000,
        montant_paye=0,
        notes=None,
        cree_par_id=accueil.id,
    )
    order_a.lignes = [
        LigneCommande(
            type_vetement_id=boubou.id,
            description=None,
            quantite=2,
            prix_unitaire=4000,
        )
    ]
    order_b1.lignes = [
        LigneCommande(
            type_vetement_id=chemise.id,
            description=None,
            quantite=1,
            prix_unitaire=1000,
        )
    ]
    order_b2.lignes = [
        LigneCommande(
            type_vetement_id=chemise.id,
            description=None,
            quantite=1,
            prix_unitaire=1000,
        )
    ]
    cancelled.lignes = [
        LigneCommande(
            type_vetement_id=boubou.id,
            description=None,
            quantite=1,
            prix_unitaire=5000,
        )
    ]
    order_a.paiements = [
        Paiement(
            montant=3000,
            mode=ModePaiement.wave,
            reference=None,
            date_paiement=today,
            enregistre_par_id=accueil.id,
        )
    ]
    order_b2.paiements = [
        Paiement(
            montant=500,
            mode=ModePaiement.especes,
            reference=None,
            date_paiement=today - timedelta(days=1),
            enregistre_par_id=accueil.id,
        )
    ]
    order_a.livraison = Livraison(
        mode=ModeLivraison.retrait_atelier,
        adresse=None,
        livreur=None,
        date_prevue=today,
        date_effective=None,
        statut=StatutLivraison.planifiee,
        notes=None,
    )
    order_b1.livraison = Livraison(
        mode=ModeLivraison.domicile,
        adresse="Dakar",
        livreur="Awa",
        date_prevue=today + timedelta(days=1),
        date_effective=None,
        statut=StatutLivraison.planifiee,
        notes=None,
    )
    session.add_all([order_a, order_b1, order_b2, cancelled])
    session.commit()

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        with TestClient(app) as test_client:
            yield test_client, session, {
                "admin": admin,
                "accueil": accueil,
                "client_a": client_a,
                "client_b": client_b,
                "orders": [order_a, order_b1, order_b2, cancelled],
            }
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


def test_dashboard_aggregates_revenue_status_debt_and_due_deliveries(
    statistiques_context,
) -> None:
    test_client, _, _ = statistiques_context
    response = test_client.get("/api/v1/statistiques/tableau-de-bord")

    assert response.status_code == 200
    dashboard = response.json()
    today = date.today()
    assert dashboard["mois"] == f"{today.year}-{today.month:02d}"
    assert dashboard["chiffre_affaires"] == 10000
    assert dashboard["encaisse"] == 3500
    assert dashboard["nb_commandes"] == 3
    assert dashboard["reste_a_encaisser"] == 7000
    assert dashboard["commandes_par_statut"] == {
        "en_attente": 1,
        "en_coupe": 0,
        "en_couture": 1,
        "essayage": 0,
        "retouches": 0,
        "terminee": 1,
        "livree": 0,
        "annulee": 1,
    }
    assert dashboard["commandes_en_retard"] == 1
    assert dashboard["commandes_pretes"] == 1
    assert dashboard["livraisons_du_jour"] == 1


def test_revenue_reports_day_and_month_periods_and_validates_range(
    statistiques_context,
) -> None:
    test_client, _, _ = statistiques_context
    today = date.today()
    yesterday = today - timedelta(days=1)

    daily = test_client.get(
        "/api/v1/statistiques/chiffre-affaires",
        params={
            "date_debut": yesterday.isoformat(),
            "date_fin": today.isoformat(),
        },
    )
    assert daily.status_code == 200
    assert daily.json() == [
        {
            "periode": yesterday.isoformat(),
            "chiffre_affaires": 0,
            "encaisse": 500,
            "nb_commandes": 0,
        },
        {
            "periode": today.isoformat(),
            "chiffre_affaires": 10000,
            "encaisse": 3000,
            "nb_commandes": 3,
        },
    ]

    monthly = test_client.get(
        "/api/v1/statistiques/chiffre-affaires",
        params={
            "date_debut": yesterday.isoformat(),
            "date_fin": today.isoformat(),
            "granularite": "mois",
        },
    )
    assert monthly.status_code == 200
    assert monthly.json() == [
        {
            "periode": f"{today.year}-{today.month:02d}",
            "chiffre_affaires": 10000,
            "encaisse": 3500,
            "nb_commandes": 3,
        }
    ]

    invalid_range = test_client.get(
        "/api/v1/statistiques/chiffre-affaires",
        params={
            "date_debut": today.isoformat(),
            "date_fin": yesterday.isoformat(),
        },
    )
    assert invalid_range.status_code == 422
    assert "date de début" in invalid_range.json()["detail"]


def test_garment_statistics_exclude_cancelled_orders_and_sort_by_revenue(
    statistiques_context,
) -> None:
    test_client, _, _ = statistiques_context

    response = test_client.get("/api/v1/statistiques/types-vetement")

    assert response.status_code == 200
    assert response.json() == [
        {
            "type_vetement_id": 1,
            "nom": "Boubou",
            "quantite": 2,
            "chiffre_affaires": 8000,
        },
        {
            "type_vetement_id": 2,
            "nom": "Chemise",
            "quantite": 2,
            "chiffre_affaires": 2000,
        },
    ]


def test_top_clients_supports_both_sort_orders_and_limit(statistiques_context) -> None:
    test_client, _, records = statistiques_context

    by_revenue = test_client.get("/api/v1/statistiques/top-clients")
    by_count = test_client.get(
        "/api/v1/statistiques/top-clients",
        params={"tri": "commandes", "limite": 1},
    )
    invalid_limit = test_client.get(
        "/api/v1/statistiques/top-clients",
        params={"limite": 101},
    )

    assert by_revenue.status_code == 200
    assert by_revenue.json()[0]["client_id"] == records["client_a"].id
    assert by_revenue.json()[0]["nb_commandes"] == 1
    assert by_revenue.json()[0]["chiffre_affaires"] == 8000
    assert by_count.status_code == 200
    assert len(by_count.json()) == 1
    assert by_count.json()[0]["client_id"] == records["client_b"].id
    assert by_count.json()[0]["nb_commandes"] == 2
    assert invalid_limit.status_code == 422


def test_unpaid_orders_are_non_cancelled_and_ordered_by_due_date(
    statistiques_context,
) -> None:
    test_client, _, records = statistiques_context

    response = test_client.get("/api/v1/statistiques/impayes")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [
        records["orders"][0].id,
        records["orders"][2].id,
        records["orders"][1].id,
    ]


def test_statistics_routes_are_admin_only(statistiques_context, monkeypatch) -> None:
    test_client, _, records = statistiques_context
    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: records["accueil"],
    )

    for path in (
        "/api/v1/statistiques/tableau-de-bord",
        "/api/v1/statistiques/chiffre-affaires?date_debut=2026-01-01&date_fin=2026-01-31",
        "/api/v1/statistiques/types-vetement",
        "/api/v1/statistiques/top-clients",
        "/api/v1/statistiques/impayes",
    ):
        response = test_client.get(path)
        assert response.status_code == 403
