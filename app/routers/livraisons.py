from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import exiger_roles, get_current_user
from app.models import Utilisateur
from app.models.enums import Role, StatutLivraison
from app.schemas.livraison import (
    LivraisonConfirmation,
    LivraisonLecture,
    LivraisonPlanification,
)
from app.services import livraison_service

router = APIRouter(tags=["Livraisons"])
accueil_requis = exiger_roles(Role.accueil)


@router.put(
    "/commandes/{commande_id}/livraison",
    response_model=LivraisonLecture,
)
def planifier_livraison(
    commande_id: int,
    donnees: LivraisonPlanification,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(accueil_requis),
) -> LivraisonLecture:
    return livraison_service.planifier(db, commande_id, donnees)


@router.get(
    "/commandes/{commande_id}/livraison",
    response_model=LivraisonLecture,
)
def lire_livraison(
    commande_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> LivraisonLecture:
    return livraison_service.obtenir(db, commande_id)


@router.post(
    "/commandes/{commande_id}/livraison/confirmer",
    response_model=LivraisonLecture,
)
def confirmer_livraison(
    commande_id: int,
    donnees: LivraisonConfirmation = LivraisonConfirmation(),
    db: Session = Depends(get_db),
    acteur: Utilisateur = Depends(accueil_requis),
) -> LivraisonLecture:
    return livraison_service.confirmer(db, commande_id, donnees, acteur)


@router.get("/livraisons", response_model=list[LivraisonLecture])
def tournee_livraisons(
    statut: StatutLivraison | None = None,
    date_min: date | None = None,
    date_max: date | None = None,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> list[LivraisonLecture]:
    return livraison_service.lister(db, statut, date_min, date_max)
