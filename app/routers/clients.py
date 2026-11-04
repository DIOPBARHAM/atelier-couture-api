from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import exiger_roles, get_current_user
from app.models import Client, Commande, Utilisateur
from app.models.enums import Genre, Role
from app.schemas.client import (
    ClientCreation,
    ClientLecture,
    ClientModification,
    ClientResume,
)
from app.schemas.commande import CommandeResume
from app.schemas.commun import Page
from app.services import client_service

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.post("", response_model=ClientLecture, status_code=201)
def creer_client(
    donnees: ClientCreation,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> Client:
    return client_service.creer(db, donnees)


@router.get("", response_model=Page[ClientLecture])
def rechercher_clients(
    q: str | None = Query(default=None, min_length=2),
    genre: Genre | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> dict[str, object]:
    return client_service.lister(db, q, genre, limit, offset)


@router.get("/{client_id}", response_model=ClientLecture)
def lire_client(
    client_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> Client:
    return client_service.obtenir(db, client_id)


@router.patch("/{client_id}", response_model=ClientLecture)
def modifier_client(
    client_id: int,
    donnees: ClientModification,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> Client:
    return client_service.modifier(db, client_id, donnees)


@router.delete("/{client_id}", status_code=204)
def supprimer_client(
    client_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(exiger_roles(Role.admin)),
) -> Response:
    client_service.supprimer(db, client_id)
    return Response(status_code=204)


@router.get("/{client_id}/commandes", response_model=Page[CommandeResume])
def commandes_du_client(
    client_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> dict[str, object]:
    return client_service.commandes_du_client(db, client_id, limit, offset)


@router.get("/{client_id}/resume", response_model=ClientResume)
def resume_client(
    client_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> dict[str, object]:
    return client_service.resume(db, client_id)
