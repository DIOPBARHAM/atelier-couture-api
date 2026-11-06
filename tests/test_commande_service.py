from collections.abc import Iterator
from datetime import date
from typing import TypedDict

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.exceptions import AccesInterdit, Conflit, DonneesInvalides
from app.models import Client, Commande, TypeVetement, Utilisateur
from app.models.enums import Genre, Role, StatutCommande
from app.schemas.commande import CommandeCreation, LigneCreation, StatutChangement
from app.services import commande_service


class DonneesCommande(TypedDict):
    accueil: Utilisateur
    tailleur: Utilisateur
    client: Client
    boubou: TypeVetement
    pantalon: TypeVetement
    ancien: TypeVetement


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def donnees(db: Session) -> DonneesCommande:
    accueil = Utilisateur(
        email="a@x.sn",
        nom_complet="Accueil",
        mot_de_passe_hash="x",
        role=Role.accueil,
        actif=True,
    )
    tailleur = Utilisateur(
        email="t@x.sn",
        nom_complet="Tailleur",
        mot_de_passe_hash="x",
        role=Role.tailleur,
        actif=True,
    )
    client = Client(
        nom="Diop",
        prenom="Fatou",
        telephone="771234567",
        genre=Genre.femme,
    )
    boubou = TypeVetement(
        nom="Boubou",
        prix_base=35000,
        delai_jours=10,
        actif=True,
    )
    pantalon = TypeVetement(
        nom="Pantalon",
        prix_base=12000,
        delai_jours=4,
        actif=True,
    )
    ancien = TypeVetement(
        nom="Ancien",
        prix_base=1000,
        delai_jours=1,
        actif=False,
    )
    db.add_all([accueil, tailleur, client, boubou, pantalon, ancien])
    db.commit()
    return {
        "accueil": accueil,
        "tailleur": tailleur,
        "client": client,
        "boubou": boubou,
        "pantalon": pantalon,
        "ancien": ancien,
    }


def _creer(
    db: Session,
    donnees: DonneesCommande,
    lignes: list[LigneCreation],
    remise: int = 0,
    date_commande: date = date(2026, 3, 1),
) -> Commande:
    creation = CommandeCreation(
        client_id=donnees["client"].id,
        remise=remise,
        date_commande=date_commande,
        lignes=lignes,
    )
    return commande_service.creer(db, creation, donnees["accueil"])


def test_calcul_du_total_avec_prix_negocie_et_remise(
    db: Session, donnees: DonneesCommande
) -> None:
    commande = _creer(
        db,
        donnees,
        [
            LigneCreation(type_vetement_id=donnees["boubou"].id, quantite=2),
            LigneCreation(
                type_vetement_id=donnees["pantalon"].id,
                quantite=1,
                prix_unitaire=10000,
            ),
        ],
        remise=5000,
    )
    assert commande.montant_total == 75000
    assert commande.solde == 75000


def test_date_prevue_utilise_le_delai_le_plus_long(
    db: Session, donnees: DonneesCommande
) -> None:
    commande = _creer(
        db,
        donnees,
        [
            LigneCreation(type_vetement_id=donnees["boubou"].id, quantite=1),
            LigneCreation(type_vetement_id=donnees["pantalon"].id, quantite=1),
        ],
    )
    assert commande.date_livraison_prevue == date(2026, 3, 11)


def test_numero_de_commande_au_bon_format_et_incremental(
    db: Session, donnees: DonneesCommande
) -> None:
    ligne = [
        LigneCreation(type_vetement_id=donnees["boubou"].id, quantite=1)
    ]
    assert _creer(db, donnees, ligne).numero == "CMD-2026-00001"
    assert _creer(db, donnees, ligne).numero == "CMD-2026-00002"


def test_creation_ajoute_l_entree_initiale_de_l_historique(
    db: Session, donnees: DonneesCommande
) -> None:
    commande = _commande_simple(db, donnees)
    assert len(commande.historique) == 1
    assert commande.historique[0].ancien_statut is None
    assert commande.historique[0].nouveau_statut == StatutCommande.en_attente


def test_remise_superieure_au_total_brut_refusee(
    db: Session, donnees: DonneesCommande
) -> None:
    with pytest.raises(DonneesInvalides):
        _creer(
            db,
            donnees,
            [
                LigneCreation(
                    type_vetement_id=donnees["pantalon"].id,
                    quantite=1,
                )
            ],
            remise=99999,
        )


def test_prestation_desactivee_non_commandable(
    db: Session, donnees: DonneesCommande
) -> None:
    with pytest.raises(DonneesInvalides):
        _creer(
            db,
            donnees,
            [
                LigneCreation(
                    type_vetement_id=donnees["ancien"].id,
                    quantite=1,
                )
            ],
        )


def _commande_simple(db: Session, donnees: DonneesCommande) -> Commande:
    return _creer(
        db,
        donnees,
        [
            LigneCreation(type_vetement_id=donnees["boubou"].id, quantite=1)
        ],
    )


def test_transition_interdite_liste_les_statuts_possibles(
    db: Session, donnees: DonneesCommande
) -> None:
    commande = _commande_simple(db, donnees)
    with pytest.raises(Conflit) as erreur:
        commande_service.changer_statut(
            db,
            commande.id,
            StatutChangement(statut=StatutCommande.terminee),
            donnees["accueil"],
        )
    assert "Statuts possibles" in erreur.value.detail
    assert "en_coupe" in erreur.value.detail


def test_statut_livree_interdit_via_le_service_de_statut(
    db: Session, donnees: DonneesCommande
) -> None:
    commande = _commande_simple(db, donnees)
    with pytest.raises(Conflit):
        commande_service.changer_statut(
            db,
            commande.id,
            StatutChangement(statut=StatutCommande.livree),
            donnees["accueil"],
        )


def test_meme_statut_refuse(db: Session, donnees: DonneesCommande) -> None:
    commande = _commande_simple(db, donnees)
    with pytest.raises(Conflit):
        commande_service.changer_statut(
            db,
            commande.id,
            StatutChangement(statut=StatutCommande.en_attente),
            donnees["accueil"],
        )


def test_le_tailleur_ne_peut_pas_annuler(
    db: Session, donnees: DonneesCommande
) -> None:
    commande = _commande_simple(db, donnees)
    with pytest.raises(AccesInterdit):
        commande_service.changer_statut(
            db,
            commande.id,
            StatutChangement(statut=StatutCommande.annulee),
            donnees["tailleur"],
        )


def test_annulation_avec_acompte_exige_un_commentaire(
    db: Session, donnees: DonneesCommande
) -> None:
    commande = _commande_simple(db, donnees)
    commande.montant_paye = 10000
    db.commit()
    with pytest.raises(DonneesInvalides):
        commande_service.changer_statut(
            db,
            commande.id,
            StatutChangement(statut=StatutCommande.annulee),
            donnees["accueil"],
        )
    resultat = commande_service.changer_statut(
        db,
        commande.id,
        StatutChangement(
            statut=StatutCommande.annulee,
            commentaire="Acompte à rembourser",
        ),
        donnees["accueil"],
    )
    assert resultat.statut == StatutCommande.annulee


def test_chaque_changement_de_statut_ecrit_l_historique(
    db: Session, donnees: DonneesCommande
) -> None:
    commande = _commande_simple(db, donnees)
    commande_service.changer_statut(
        db,
        commande.id,
        StatutChangement(statut=StatutCommande.en_coupe),
        donnees["tailleur"],
    )
    resultat = commande_service.changer_statut(
        db,
        commande.id,
        StatutChangement(statut=StatutCommande.en_couture),
        donnees["tailleur"],
    )
    assert [h.nouveau_statut for h in resultat.historique] == [
        StatutCommande.en_attente,
        StatutCommande.en_coupe,
        StatutCommande.en_couture,
    ]
