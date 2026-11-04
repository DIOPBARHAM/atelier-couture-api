from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import exiger_roles, get_current_user
from app.models import Utilisateur
from app.models.enums import Role
from app.schemas.paiement import PaiementCreation, PaiementLecture
from app.services import paiement_service

router = APIRouter(tags=["Paiements"])


@router.post(
    "/commandes/{commande_id}/paiements",
    response_model=PaiementLecture,
    status_code=201,
)
def enregistrer_paiement(
    commande_id: int,
    donnees: PaiementCreation,
    db: Session = Depends(get_db),
    acteur: Utilisateur = Depends(exiger_roles(Role.accueil)),
) -> PaiementLecture:
    return paiement_service.enregistrer(db, commande_id, donnees, acteur)


@router.get(
    "/commandes/{commande_id}/paiements",
    response_model=list[PaiementLecture],
)
def lister_paiements(
    commande_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> list[PaiementLecture]:
    return paiement_service.lister(db, commande_id)


@router.delete("/paiements/{paiement_id}", status_code=204)
def annuler_paiement(
    paiement_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(exiger_roles(Role.admin)),
) -> Response:
    paiement_service.annuler(db, paiement_id)
    return Response(status_code=204)
