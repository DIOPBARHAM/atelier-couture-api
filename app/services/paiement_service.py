from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import Conflit, DonneesInvalides, NonTrouve
from app.models import Commande, Paiement, Utilisateur
from app.models.enums import StatutCommande
from app.schemas.paiement import PaiementCreation
from app.services import commande_service


def enregistrer(
    db: Session,
    commande_id: int,
    donnees: PaiementCreation,
    acteur: Utilisateur,
) -> Paiement:
    commande = commande_service.obtenir(db, commande_id)

    if commande.statut == StatutCommande.annulee:
        raise Conflit("Impossible d'enregistrer un paiement sur une commande annulée")

    date_paiement = donnees.date_paiement or date.today()
    if date_paiement > date.today():
        raise DonneesInvalides("La date de paiement ne peut pas être dans le futur")

    solde = commande.solde
    if donnees.montant > solde:
        raise Conflit(
            f"Le montant ({donnees.montant} FCFA) dépasse le solde restant "
            f"({solde} FCFA)"
        )

    paiement = Paiement(
        montant=donnees.montant,
        mode=donnees.mode,
        reference=donnees.reference,
        date_paiement=date_paiement,
        enregistre_par_id=acteur.id,
    )
    commande.paiements.append(paiement)
    commande_service.recalculer(commande)
    db.commit()
    db.refresh(paiement)
    return paiement


def lister(db: Session, commande_id: int) -> list[Paiement]:
    commande_service.obtenir(db, commande_id)
    return list(
        db.scalars(
            select(Paiement)
            .where(Paiement.commande_id == commande_id)
            .order_by(Paiement.date_paiement, Paiement.id)
        )
    )


def annuler(db: Session, paiement_id: int) -> None:
    paiement = db.get(Paiement, paiement_id)
    if paiement is None:
        raise NonTrouve("Paiement introuvable")

    commande = db.get(Commande, paiement.commande_id)
    if commande is None:
        raise NonTrouve("Commande introuvable")

    db.delete(paiement)
    db.flush()
    db.expire(commande, ["paiements"])
    commande_service.recalculer(commande)
    db.commit()
