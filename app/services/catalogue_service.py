from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import Conflit, NonTrouve
from app.models import TypeVetement
from app.schemas.catalogue import TypeVetementCreation, TypeVetementModification


def _nom_existe(db: Session, nom: str, sauf_id: int | None = None) -> bool:
    stmt = select(TypeVetement.id).where(TypeVetement.nom == nom)
    if sauf_id is not None:
        stmt = stmt.where(TypeVetement.id != sauf_id)
    return db.scalar(stmt) is not None


def creer(db: Session, donnees: TypeVetementCreation) -> TypeVetement:
    if _nom_existe(db, donnees.nom):
        raise Conflit("Une prestation existe déjà avec ce nom")
    prestation = TypeVetement(**donnees.model_dump(), actif=True)
    db.add(prestation)
    db.commit()
    db.refresh(prestation)
    return prestation


def lister(db: Session, actifs_seulement: bool) -> list[TypeVetement]:
    stmt = select(TypeVetement).order_by(TypeVetement.nom)
    if actifs_seulement:
        stmt = stmt.where(TypeVetement.actif.is_(True))
    return list(db.scalars(stmt))


def obtenir(db: Session, prestation_id: int) -> TypeVetement:
    prestation = db.get(TypeVetement, prestation_id)
    if prestation is None:
        raise NonTrouve("Prestation introuvable")
    return prestation


def modifier(
    db: Session,
    prestation_id: int,
    donnees: TypeVetementModification,
) -> TypeVetement:
    prestation = obtenir(db, prestation_id)
    changements = donnees.model_dump(exclude_unset=True)
    if "nom" in changements and changements["nom"] is not None:
        if _nom_existe(db, changements["nom"], sauf_id=prestation.id):
            raise Conflit("Une prestation existe déjà avec ce nom")
    for champ, valeur in changements.items():
        if valeur is not None or champ == "description":
            setattr(prestation, champ, valeur)
    db.commit()
    db.refresh(prestation)
    return prestation
