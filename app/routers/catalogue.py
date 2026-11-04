from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import exiger_roles, get_current_user
from app.models import TypeVetement, Utilisateur
from app.models.enums import Role
from app.schemas.catalogue import (
    TypeVetementCreation,
    TypeVetementLecture,
    TypeVetementModification,
)
from app.services import catalogue_service

router = APIRouter(prefix="/catalogue", tags=["Catalogue"])
admin_requis = exiger_roles(Role.admin)


@router.post("", response_model=TypeVetementLecture, status_code=201)
def ajouter_prestation(
    donnees: TypeVetementCreation,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(admin_requis),
) -> TypeVetement:
    return catalogue_service.creer(db, donnees)


@router.get("", response_model=list[TypeVetementLecture])
def lister_prestations(
    actifs_seulement: bool = True,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> list[TypeVetement]:
    return catalogue_service.lister(db, actifs_seulement)


@router.get("/{prestation_id}", response_model=TypeVetementLecture)
def lire_prestation(
    prestation_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> TypeVetement:
    return catalogue_service.obtenir(db, prestation_id)


@router.patch("/{prestation_id}", response_model=TypeVetementLecture)
def modifier_prestation(
    prestation_id: int,
    donnees: TypeVetementModification,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(admin_requis),
) -> TypeVetement:
    return catalogue_service.modifier(db, prestation_id, donnees)
