from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import exiger_roles, get_current_user
from app.models import Mesure, Utilisateur
from app.models.enums import Role
from app.schemas.mesure import MesureCreation, MesureLecture, MesureModification
from app.services import mesure_service

router = APIRouter(tags=["Mesures"])
tailleur_requis = exiger_roles(Role.tailleur)


@router.post(
    "/clients/{client_id}/mesures",
    response_model=MesureLecture,
    status_code=201,
)
def saisir_mesures(
    client_id: int,
    donnees: MesureCreation,
    db: Session = Depends(get_db),
    acteur: Utilisateur = Depends(tailleur_requis),
) -> Mesure:
    return mesure_service.creer(db, client_id, donnees, acteur)


@router.get(
    "/clients/{client_id}/mesures",
    response_model=list[MesureLecture],
)
def historique_mesures(
    client_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> list[Mesure]:
    return mesure_service.lister(db, client_id)


@router.get(
    "/clients/{client_id}/mesures/derniere",
    response_model=MesureLecture,
)
def dernieres_mesures(
    client_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> Mesure:
    return mesure_service.derniere(db, client_id)


@router.get("/mesures/{mesure_id}", response_model=MesureLecture)
def lire_mesure(
    mesure_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> Mesure:
    return mesure_service.obtenir(db, mesure_id)


@router.patch("/mesures/{mesure_id}", response_model=MesureLecture)
def corriger_mesure(
    mesure_id: int,
    donnees: MesureModification,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(tailleur_requis),
) -> Mesure:
    return mesure_service.modifier(db, mesure_id, donnees)


@router.delete("/mesures/{mesure_id}", status_code=204)
def supprimer_mesure(
    mesure_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(tailleur_requis),
) -> Response:
    mesure_service.supprimer(db, mesure_id)
    return Response(status_code=204)
