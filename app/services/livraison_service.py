from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import Conflit, DonneesInvalides, NonTrouve
from app.models import HistoriqueStatut, Livraison, Utilisateur
from app.models.enums import ModeLivraison, StatutCommande, StatutLivraison
from app.schemas.livraison import LivraisonConfirmation, LivraisonPlanification
from app.services import commande_service


def planifier(
    db: Session,
    commande_id: int,
    donnees: LivraisonPlanification,
) -> Livraison:
    """RG18 : crée la livraison, ou modifie l'existante en cas de replanification."""
    commande = commande_service.obtenir(db, commande_id)
    if commande.statut in commande_service.STATUTS_FINAUX:
        raise Conflit(
            f"Commande {commande.statut.value} : planification de livraison impossible"
        )

    adresse = (donnees.adresse or "").strip() or None
    if donnees.mode == ModeLivraison.domicile and adresse is None:
        raise DonneesInvalides("Une livraison à domicile exige une adresse")

    date_prevue = donnees.date_prevue or commande.date_livraison_prevue
    if date_prevue < commande.date_commande:
        raise DonneesInvalides(
            "La date de livraison prévue ne peut pas précéder la date de commande"
        )

    livraison = commande.livraison
    if livraison is None:
        livraison = Livraison(commande_id=commande.id)
        commande.livraison = livraison
    livraison.mode = donnees.mode
    livraison.adresse = adresse
    livraison.livreur = donnees.livreur
    livraison.date_prevue = date_prevue
    livraison.notes = donnees.notes
    livraison.statut = StatutLivraison.planifiee

    db.commit()
    db.refresh(livraison)
    return livraison


def obtenir(db: Session, commande_id: int) -> Livraison:
    commande = commande_service.obtenir(db, commande_id)
    if commande.livraison is None:
        raise NonTrouve("Aucune livraison planifiée pour cette commande")
    return commande.livraison


def confirmer(
    db: Session,
    commande_id: int,
    donnees: LivraisonConfirmation,
    acteur: Utilisateur,
) -> Livraison:
    commande = commande_service.obtenir(db, commande_id)

    if commande.statut != StatutCommande.terminee:
        raise Conflit(
            "Confirmation impossible : la commande doit être au statut terminee "
            f"(statut actuel : {commande.statut.value})"
        )
    solde = commande.solde
    if solde > 0 and not donnees.autoriser_solde_impaye:
        raise Conflit(
            f"Confirmation impossible : il reste {solde} FCFA à payer. "
            "Encaissez le solde ou confirmez avec autoriser_solde_impaye"
        )

    aujourdhui = date.today()
    livraison = commande.livraison
    if livraison is None:
        livraison = Livraison(
            commande_id=commande.id,
            mode=ModeLivraison.retrait_atelier,
            date_prevue=aujourdhui,
        )
        commande.livraison = livraison
    livraison.statut = StatutLivraison.livree
    livraison.date_effective = aujourdhui

    commande.statut = StatutCommande.livree
    commande.date_livraison_reelle = aujourdhui
    commentaire = "Livraison confirmée"
    if solde > 0:
        commentaire += f" avec un solde impayé de {solde} FCFA"
    commande.historique.append(
        HistoriqueStatut(
            ancien_statut=StatutCommande.terminee,
            nouveau_statut=StatutCommande.livree,
            commentaire=commentaire,
            utilisateur_id=acteur.id,
        )
    )
    db.commit()
    db.refresh(livraison)
    return livraison


def lister(
    db: Session,
    statut: StatutLivraison | None,
    date_min: date | None,
    date_max: date | None,
) -> list[Livraison]:
    requete = select(Livraison)
    if statut is not None:
        requete = requete.where(Livraison.statut == statut)
    if date_min is not None:
        requete = requete.where(Livraison.date_prevue >= date_min)
    if date_max is not None:
        requete = requete.where(Livraison.date_prevue <= date_max)
    return list(
        db.scalars(requete.order_by(Livraison.date_prevue, Livraison.id))
    )
