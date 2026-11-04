from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import Conflit, NonTrouve
from app.models import Utilisateur
from app.models.enums import Role
from app.schemas.utilisateur import UtilisateurCreation, UtilisateurModification
from app.security import hasher_mot_de_passe


def creer(db: Session, donnees: UtilisateurCreation) -> Utilisateur:
    email = donnees.email.strip().lower()
    if db.scalar(select(Utilisateur).where(Utilisateur.email == email)) is not None:
        raise Conflit("Un compte existe déjà avec cet email")
    utilisateur = Utilisateur(
        email=email,
        nom_complet=donnees.nom_complet.strip(),
        mot_de_passe_hash=hasher_mot_de_passe(donnees.mot_de_passe),
        role=donnees.role,
        actif=True,
    )
    db.add(utilisateur)
    db.commit()
    db.refresh(utilisateur)
    return utilisateur


def lister(db: Session) -> list[Utilisateur]:
    return list(db.scalars(select(Utilisateur).order_by(Utilisateur.nom_complet)))


def obtenir(db: Session, utilisateur_id: int) -> Utilisateur:
    utilisateur = db.get(Utilisateur, utilisateur_id)
    if utilisateur is None:
        raise NonTrouve("Utilisateur introuvable")
    return utilisateur


def modifier(
    db: Session,
    utilisateur_id: int,
    donnees: UtilisateurModification,
    acteur: Utilisateur,
) -> Utilisateur:
    utilisateur = obtenir(db, utilisateur_id)
    changements = donnees.model_dump(exclude_unset=True)

    if utilisateur.id == acteur.id:
        if changements.get("actif") is False:
            raise Conflit("Un administrateur ne peut pas désactiver son propre compte")
        if changements.get("role") not in (None, Role.admin):
            raise Conflit("Un administrateur ne peut pas retirer son propre rôle admin")

    mot_de_passe = changements.pop("mot_de_passe", None)
    if mot_de_passe is not None:
        utilisateur.mot_de_passe_hash = hasher_mot_de_passe(mot_de_passe)

    for champ, valeur in changements.items():
        if valeur is not None:
            setattr(utilisateur, champ, valeur)

    db.commit()
    db.refresh(utilisateur)
    return utilisateur
