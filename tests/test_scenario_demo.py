from collections.abc import Callable, Iterator
from datetime import date, timedelta

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

P = "/api/v1"


@pytest.fixture
def demo() -> Iterator[tuple[Callable[[Role], TestClient], dict[str, int]]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)

    utilisateurs = {
        role: Utilisateur(
            email=f"{role.value}-demo@example.com",
            nom_complet=role.value.capitalize(),
            mot_de_passe_hash="unused",
            role=role,
            actif=True,
        )
        for role in Role
    }
    catalogue = [
        TypeVetement(nom="Boubou", prix_base=35000, delai_jours=10, actif=True),
        TypeVetement(nom="Pantalon", prix_base=12000, delai_jours=4, actif=True),
        TypeVetement(nom="Chemise", prix_base=15000, delai_jours=5, actif=True),
    ]
    session.add_all([*utilisateurs.values(), *catalogue])
    session.commit()

    def get_test_db() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = get_test_db
    client = TestClient(app)

    def comme(role: Role) -> TestClient:
        """Fait agir le client de test sous le rôle demandé."""
        app.dependency_overrides[get_current_user] = lambda: utilisateurs[role]
        return client

    try:
        yield comme, {prestation.nom: prestation.id for prestation in catalogue}
    finally:
        app.dependency_overrides.clear()
        client.close()
        session.close()
        engine.dispose()


def test_scenario_de_demonstration_annexe_a(demo) -> None:
    comme, ids = demo
    aujourdhui = date.today()

    fatou = {
        "nom": "Diop",
        "prenom": "Fatou",
        "telephone": "77 123 45 67",
        "genre": "femme",
    }
    reponse = comme(Role.accueil).post(f"{P}/clients", json=fatou)
    assert reponse.status_code == 201
    client_id = reponse.json()["id"]
    doublon = comme(Role.accueil).post(
        f"{P}/clients",
        json={**fatou, "telephone": "771234567"},
    )
    assert doublon.status_code == 409

    mesures = {"tour_poitrine": 98, "tour_taille": 82, "longueur_manche": 62}
    refus = comme(Role.accueil).post(
        f"{P}/clients/{client_id}/mesures",
        json=mesures,
    )
    assert refus.status_code == 403
    reponse = comme(Role.tailleur).post(
        f"{P}/clients/{client_id}/mesures",
        json=mesures,
    )
    assert reponse.status_code == 201
    mesure_id = reponse.json()["id"]

    avant = comme(Role.admin).get(f"{P}/statistiques/tableau-de-bord").json()

    reponse = comme(Role.accueil).post(
        f"{P}/commandes",
        json={
            "client_id": client_id,
            "remise": 5000,
            "lignes": [
                {"type_vetement_id": ids["Boubou"], "quantite": 2},
                {
                    "type_vetement_id": ids["Pantalon"],
                    "quantite": 1,
                    "prix_unitaire": 10000,
                },
            ],
        },
    )
    assert reponse.status_code == 201
    commande = reponse.json()
    commande_id = commande["id"]
    assert commande["numero"].startswith(f"CMD-{aujourdhui.year}-")
    assert commande["statut"] == "en_attente"
    assert commande["montant_total"] == 2 * 35000 + 10000 - 5000
    assert commande["solde"] == 75000
    assert commande["date_livraison_prevue"] == (
        aujourdhui + timedelta(days=10)
    ).isoformat()
    assert commande["mesure_id"] == mesure_id
    assert len(commande["lignes"]) == 2

    reponse = comme(Role.accueil).post(
        f"{P}/commandes/{commande_id}/statut",
        json={"statut": "terminee"},
    )
    assert reponse.status_code == 409
    assert "Statuts possibles : annulee, en_coupe" in reponse.json()["detail"]

    parcours = [
        "en_coupe",
        "en_couture",
        "essayage",
        "retouches",
        "essayage",
        "terminee",
    ]
    for statut in parcours:
        reponse = comme(Role.tailleur).post(
            f"{P}/commandes/{commande_id}/statut",
            json={"statut": statut},
        )
        assert reponse.status_code == 200, statut
    historique = comme(Role.tailleur).get(
        f"{P}/commandes/{commande_id}/historique"
    ).json()
    assert len(historique) == 7
    assert historique[0]["ancien_statut"] is None
    assert [entree["nouveau_statut"] for entree in historique] == [
        "en_attente",
        *parcours,
    ]

    reponse = comme(Role.accueil).post(
        f"{P}/commandes/{commande_id}/paiements",
        json={"montant": 20000, "mode": "wave", "reference": "WV-001"},
    )
    assert reponse.status_code == 201
    trop = comme(Role.accueil).post(
        f"{P}/commandes/{commande_id}/paiements",
        json={"montant": 100000, "mode": "wave"},
    )
    assert trop.status_code == 409

    reponse = comme(Role.accueil).post(
        f"{P}/commandes/{commande_id}/livraison/confirmer",
        json={},
    )
    assert reponse.status_code == 409

    reponse = comme(Role.accueil).post(
        f"{P}/commandes/{commande_id}/paiements",
        json={"montant": 55000, "mode": "especes"},
    )
    assert reponse.status_code == 201
    reponse = comme(Role.accueil).post(
        f"{P}/commandes/{commande_id}/livraison/confirmer",
        json={},
    )
    assert reponse.status_code == 200
    final = comme(Role.accueil).get(f"{P}/commandes/{commande_id}").json()
    assert final["statut"] == "livree"
    assert final["solde"] == 0
    assert final["date_livraison_reelle"] == aujourdhui.isoformat()

    apres = comme(Role.admin).get(f"{P}/statistiques/tableau-de-bord").json()
    assert apres["chiffre_affaires"] == avant["chiffre_affaires"] + 75000
    assert apres["encaisse"] == avant["encaisse"] + 75000
    interdit = comme(Role.accueil).get(f"{P}/statistiques/tableau-de-bord")
    assert interdit.status_code == 403

    ancienne = comme(Role.accueil).post(
        f"{P}/commandes",
        json={
            "client_id": client_id,
            "date_commande": (aujourdhui - timedelta(days=30)).isoformat(),
            "lignes": [{"type_vetement_id": ids["Chemise"], "quantite": 1}],
        },
    )
    assert ancienne.status_code == 201
    ancienne_id = ancienne.json()["id"]

    impayes = comme(Role.admin).get(f"{P}/statistiques/impayes").json()
    assert [commande["id"] for commande in impayes] == [ancienne_id]
    assert impayes[0]["en_retard"] is True

    en_retard = comme(Role.admin).get(
        f"{P}/commandes",
        params={"en_retard": True},
    ).json()
    assert en_retard["total"] == 1
    assert en_retard["items"][0]["id"] == ancienne_id
