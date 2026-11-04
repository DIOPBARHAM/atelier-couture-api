from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import exiger_roles
from app.models import Utilisateur
from app.models.enums import Role
from app.schemas.utilisateur import (
    UtilisateurCreation,
    UtilisateurLecture,
    UtilisateurModification,
)
from app.services import utilisateur_service

router = APIRouter(prefix="/utilisateurs", tags=["Utilisateurs"])
admin_requis = exiger_roles(Role.admin)


@router.post("", response_model=UtilisateurLecture, status_code=201)
def creer_utilisateur(
    donnees: UtilisateurCreation,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(admin_requis),
) -> Utilisateur:
    return utilisateur_service.creer(db, donnees)


@router.get("", response_model=list[UtilisateurLecture])
def lister_utilisateurs(
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(admin_requis),
) -> list[Utilisateur]:
    return utilisateur_service.lister(db)


@router.get("/{utilisateur_id}", response_model=UtilisateurLecture)
def lire_utilisateur(
    utilisateur_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(admin_requis),
) -> Utilisateur:
    return utilisateur_service.obtenir(db, utilisateur_id)


@router.patch("/{utilisateur_id}", response_model=UtilisateurLecture)
def modifier_utilisateur(
    utilisateur_id: int,
    donnees: UtilisateurModification,
    db: Session = Depends(get_db),
    acteur: Utilisateur = Depends(admin_requis),
) -> Utilisateur:
    return utilisateur_service.modifier(db, utilisateur_id, donnees, acteur)
