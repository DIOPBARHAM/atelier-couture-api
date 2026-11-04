from itertools import product

from app.models.enums import StatutCommande as S
from app.services.commande_service import TRANSITIONS


GRAPHE_SPEC = {
    S.en_attente: {S.en_coupe, S.annulee},
    S.en_coupe: {S.en_couture, S.annulee},
    S.en_couture: {S.essayage, S.terminee, S.annulee},
    S.essayage: {S.retouches, S.terminee, S.annulee},
    S.retouches: {S.essayage, S.terminee, S.annulee},
    S.terminee: {S.livree},
    S.livree: set(),
    S.annulee: set(),
}


def test_le_graphe_correspond_a_la_specification() -> None:
    assert TRANSITIONS == GRAPHE_SPEC


def test_tout_statut_possede_une_entree_dans_le_graphe() -> None:
    assert set(TRANSITIONS) == set(S)


def test_les_statuts_finaux_n_ont_aucune_sortie() -> None:
    assert TRANSITIONS[S.livree] == set()
    assert TRANSITIONS[S.annulee] == set()


def test_seule_la_confirmation_de_livraison_mene_a_livree() -> None:
    entrees = [
        depart
        for depart, arrivees in TRANSITIONS.items()
        if S.livree in arrivees
    ]
    assert entrees == [S.terminee]


def test_aucune_transition_vers_soi_meme() -> None:
    for depart, arrivee in product(S, S):
        if depart == arrivee:
            assert arrivee not in TRANSITIONS[depart]
