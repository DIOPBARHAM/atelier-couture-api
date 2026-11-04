from datetime import date, timedelta

import pytest

from app.models.enums import Role
from tests.test_scenario_demo import P, demo  # noqa: F401


def _creer_client(comme, telephone="771234567"):
    reponse = comme(Role.accueil).post(
        f"{P}/clients",
        json={
            "nom": "Diop",
            "prenom": "Fatou",
            "telephone": telephone,
            "genre": "femme",
        },
    )
    assert reponse.status_code == 201
    return reponse.json()["id"]


def _creer_commande(comme, ids, client_id, **extra):
    reponse = comme(Role.accueil).post(
        f"{P}/commandes",
        json={
            "client_id": client_id,
            "lignes": [{"type_vetement_id": ids["Boubou"], "quantite": 2}],
            **extra,
        },
    )
    assert reponse.status_code == 201
    return reponse.json()


def _statut(comme, role, commande_id, statut, **extra):
    return comme(role).post(
        f"{P}/commandes/{commande_id}/statut",
        json={"statut": statut, **extra},
    )


def test_commande_annulee_n_est_plus_modifiable(demo):
    comme, ids = demo
    commande = _creer_commande(comme, ids, _creer_client(comme))

    assert _statut(comme, Role.accueil, commande["id"], "annulee").status_code == 200
    reponse = comme(Role.accueil).patch(
        f"{P}/commandes/{commande['id']}",
        json={"remise": 0},
    )
    assert reponse.status_code == 409


def test_filtres_de_la_liste_des_commandes(demo):
    comme, ids = demo
    aujourdhui = date.today()
    client_1 = _creer_client(comme, "771234567")
    client_2 = _creer_client(comme, "772223344")
    recente = _creer_commande(comme, ids, client_1)
    ancienne = _creer_commande(
        comme,
        ids,
        client_2,
        date_commande=(aujourdhui - timedelta(days=10)).isoformat(),
    )
    limite = (aujourdhui - timedelta(days=5)).isoformat()

    def ids_pour(**filtres):
        reponse = comme(Role.accueil).get(f"{P}/commandes", params=filtres)
        assert reponse.status_code == 200
        return [commande["id"] for commande in reponse.json()["items"]]

    assert ids_pour(client_id=client_2) == [ancienne["id"]]
    assert ids_pour(date_min=limite) == [recente["id"]]
    assert ids_pour(date_max=limite) == [ancienne["id"]]


def test_modification_d_une_commande_avec_mesure_et_valeurs_invalides(demo):
    comme, ids = demo
    client_id = _creer_client(comme)
    commande = _creer_commande(comme, ids, client_id)
    url = f"{P}/commandes/{commande['id']}"

    mesure = comme(Role.tailleur).post(
        f"{P}/clients/{client_id}/mesures",
        json={"tour_taille": 80},
    )
    assert mesure.status_code == 201
    mesure_id = mesure.json()["id"]

    reponse = comme(Role.accueil).patch(url, json={"mesure_id": mesure_id})
    assert reponse.status_code == 200
    assert reponse.json()["mesure_id"] == mesure_id

    assert comme(Role.accueil).patch(url, json={"mesure_id": 9999}).status_code == 422
    assert comme(Role.accueil).patch(
        url,
        json={"date_livraison_prevue": "2020-01-01"},
    ).status_code == 422
    assert comme(Role.accueil).patch(url, json={"remise": 999999}).status_code == 422
    assert comme(Role.accueil).patch(url, json={"remise": None}).status_code == 422


def test_suppression_d_une_ligne_inconnue(demo):
    comme, ids = demo
    commande = _creer_commande(comme, ids, _creer_client(comme))
    reponse = comme(Role.accueil).delete(
        f"{P}/commandes/{commande['id']}/lignes/9999"
    )
    assert reponse.status_code == 404


def test_message_des_statuts_possibles_depuis_terminee(demo):
    comme, ids = demo
    commande = _creer_commande(comme, ids, _creer_client(comme))
    for statut in ("en_coupe", "en_couture", "terminee"):
        assert _statut(comme, Role.tailleur, commande["id"], statut).status_code == 200

    reponse = _statut(comme, Role.tailleur, commande["id"], "en_coupe")
    assert reponse.status_code == 409
    assert (
        "livree (uniquement via la confirmation de livraison)"
        in reponse.json()["detail"]
    )


def test_paiements_d_une_commande_inconnue(demo):
    comme, _ = demo
    assert comme(Role.accueil).get(f"{P}/commandes/9999/paiements").status_code == 404
    reponse = comme(Role.accueil).post(
        f"{P}/commandes/9999/paiements",
        json={"montant": 1000, "mode": "wave"},
    )
    assert reponse.status_code == 404


def test_filtre_par_dates_de_la_tournee_de_livraison(demo):
    comme, ids = demo
    aujourdhui = date.today()
    commande = _creer_commande(comme, ids, _creer_client(comme))
    reponse = comme(Role.accueil).put(
        f"{P}/commandes/{commande['id']}/livraison",
        json={
            "mode": "retrait_atelier",
            "date_prevue": (aujourdhui + timedelta(days=3)).isoformat(),
        },
    )
    assert reponse.status_code == 200

    def nombre(**filtres):
        reponse = comme(Role.accueil).get(f"{P}/livraisons", params=filtres)
        assert reponse.status_code == 200
        return len(reponse.json())

    assert (
        nombre(
            date_min=aujourdhui.isoformat(),
            date_max=(aujourdhui + timedelta(days=5)).isoformat(),
        )
        == 1
    )
    assert nombre(date_max=aujourdhui.isoformat()) == 0


def _commande_invalide(ids, **champs):
    base = {
        "client_id": 1,
        "lignes": [{"type_vetement_id": ids["Boubou"], "quantite": 1}],
    }
    return {**base, **champs}


@pytest.mark.parametrize(
    "methode, chemin, corps, fragment",
    [
        (
            "post",
            "/commandes",
            lambda ids: _commande_invalide(
                ids,
                lignes=[{"type_vetement_id": ids["Boubou"], "quantite": 0}],
            ),
            "supérieur ou égal à 1",
        ),
        (
            "post",
            "/commandes",
            lambda ids: _commande_invalide(ids, lignes="abc"),
            "doit être une liste",
        ),
        (
            "post",
            "/commandes",
            lambda ids: _commande_invalide(ids, notes=123),
            "doit être un texte",
        ),
        (
            "post",
            "/commandes/1/livraison/confirmer",
            lambda ids: {"autoriser_solde_impaye": "peut-être"},
            "vrai ou faux",
        ),
        (
            "put",
            "/commandes/1/livraison",
            lambda ids: {"mode": "retrait_atelier", "date_prevue": "demain"},
            "AAAA-MM-JJ",
        ),
    ],
)
def test_messages_de_validation_en_francais(
    demo,
    methode,
    chemin,
    corps,
    fragment,
):
    comme, ids = demo
    reponse = getattr(comme(Role.accueil), methode)(
        f"{P}{chemin}",
        json=corps(ids),
    )
    assert reponse.status_code == 422
    assert fragment in str(reponse.json())


def test_corps_json_invalide(demo):
    comme, _ = demo
    reponse = comme(Role.accueil).post(
        f"{P}/clients",
        content="{pas du json",
        headers={"Content-Type": "application/json"},
    )
    assert reponse.status_code == 422
    assert "pas un JSON valide" in str(reponse.json())
