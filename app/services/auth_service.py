from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Utilisateur
from app.security import verifier_mot_de_passe


def authentifier(
    db: Session, email: str, mot_de_passe: str
) -> Utilisateur | None:
    """Retourne l'utilisateur si ses identifiants sont valides et son compte actif."""
    utilisateur = db.scalar(
        select(Utilisateur).where(Utilisateur.email == email.strip().lower())
    )
    if utilisateur is None:
        return None
    if not verifier_mot_de_passe(mot_de_passe, utilisateur.mot_de_passe_hash):
        return None
    if not utilisateur.actif:
        return None
    return utilisateur
