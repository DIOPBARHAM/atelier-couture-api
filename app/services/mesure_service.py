from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import Conflit, DonneesInvalides, NonTrouve
from app.models import Client, Commande, Mesure, Utilisateur
from app.models.mesure import CHAMPS_MESURES
from app.schemas.mesure import MesureCreation, MesureModification


def _verifier_client(db: Session, client_id: int) -> None:
    if db.get(Client, client_id) is None:
        raise NonTrouve("Client introuvable")


def creer(
    db: Session,
    client_id: int,
    donnees: MesureCreation,
    acteur: Utilisateur,
) -> Mesure:
    _verifier_client(db, client_id)
    valeurs = donnees.model_dump(exclude={"date_prise"})
    mesure = Mesure(
        client_id=client_id,
        prise_par_id=acteur.id,
        date_prise=donnees.date_prise or date.today(),
        **valeurs,
    )
    db.add(mesure)
    db.commit()
    db.refresh(mesure)
    return mesure


def lister(db: Session, client_id: int) -> list[Mesure]:
    """RG3 : retourne l'historique de la prise la plus récente à la plus ancienne."""
    _verifier_client(db, client_id)
    return list(
        db.scalars(
            select(Mesure)
            .where(Mesure.client_id == client_id)
            .order_by(Mesure.date_prise.desc(), Mesure.id.desc())
        )
    )


def derniere(db: Session, client_id: int) -> Mesure:
    mesures = lister(db, client_id)
    if not mesures:
        raise NonTrouve("Aucune mesure enregistrée pour ce client")
    return mesures[0]


def obtenir(db: Session, mesure_id: int) -> Mesure:
    mesure = db.get(Mesure, mesure_id)
    if mesure is None:
        raise NonTrouve("Prise de mesures introuvable")
    return mesure


def modifier(
    db: Session,
    mesure_id: int,
    donnees: MesureModification,
) -> Mesure:
    mesure = obtenir(db, mesure_id)
    changements = donnees.model_dump(exclude_unset=True)

    apres = {champ: getattr(mesure, champ) for champ in CHAMPS_MESURES}
    apres.update(
        {champ: valeur for champ, valeur in changements.items() if champ in CHAMPS_MESURES}
    )
    if all(valeur is None for valeur in apres.values()):
        raise DonneesInvalides(
            "Une prise de mesures doit conserver au moins une mesure"
        )

    for champ, valeur in changements.items():
        setattr(mesure, champ, valeur)
    db.commit()
    db.refresh(mesure)
    return mesure


def supprimer(db: Session, mesure_id: int) -> None:
    mesure = obtenir(db, mesure_id)
    utilisee = db.scalar(
        select(Commande.id)
        .where(Commande.mesure_id == mesure_id)
        .limit(1)
    )
    if utilisee is not None:
        raise Conflit(
            "Suppression impossible : ces mesures sont rattachées à une commande"
        )
    db.delete(mesure)
    db.commit()
