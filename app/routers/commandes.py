from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import exiger_roles, get_current_user
from app.models import Commande, HistoriqueStatut, Utilisateur
from app.models.enums import Role, StatutCommande
from app.schemas.commande import (
    CommandeCreation,
    CommandeDetail,
    CommandeModification,
    CommandeResume,
    HistoriqueLecture,
    LigneCreation,
    StatutChangement,
)
from app.schemas.commun import Page
from app.services import commande_service

router = APIRouter(prefix="/commandes", tags=["Commandes"])
accueil_requis = exiger_roles(Role.accueil)


@router.post("", response_model=CommandeDetail, status_code=201)
def creer_commande(
    donnees: CommandeCreation,
    db: Session = Depends(get_db),
    acteur: Utilisateur = Depends(accueil_requis),
) -> Commande:
    return commande_service.creer(db, donnees, acteur)


@router.get("", response_model=Page[CommandeResume])
def lister_commandes(
    statut: StatutCommande | None = None,
    client_id: int | None = None,
    en_retard: bool | None = None,
    date_min: date | None = None,
    date_max: date | None = None,
    numero: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> dict[str, object]:
    return commande_service.lister(
        db,
        statut,
        client_id,
        en_retard,
        date_min,
        date_max,
        numero,
        limit,
        offset,
    )


@router.get("/{commande_id}", response_model=CommandeDetail)
def lire_commande(
    commande_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> Commande:
    return commande_service.obtenir(db, commande_id)


@router.patch("/{commande_id}", response_model=CommandeDetail)
def modifier_commande(
    commande_id: int,
    donnees: CommandeModification,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(accueil_requis),
) -> Commande:
    return commande_service.modifier(db, commande_id, donnees)


@router.post(
    "/{commande_id}/lignes",
    response_model=CommandeDetail,
    status_code=201,
)
def ajouter_ligne(
    commande_id: int,
    donnees: LigneCreation,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(accueil_requis),
) -> Commande:
    return commande_service.ajouter_ligne(db, commande_id, donnees)


@router.delete(
    "/{commande_id}/lignes/{ligne_id}",
    response_model=CommandeDetail,
)
def supprimer_ligne(
    commande_id: int,
    ligne_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(accueil_requis),
) -> Commande:
    return commande_service.supprimer_ligne(db, commande_id, ligne_id)


@router.post("/{commande_id}/statut", response_model=CommandeDetail)
def changer_statut(
    commande_id: int,
    donnees: StatutChangement,
    db: Session = Depends(get_db),
    acteur: Utilisateur = Depends(get_current_user),
) -> Commande:
    return commande_service.changer_statut(db, commande_id, donnees, acteur)


@router.get(
    "/{commande_id}/historique",
    response_model=list[HistoriqueLecture],
)
def historique_commande(
    commande_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(get_current_user),
) -> list[HistoriqueStatut]:
    return commande_service.obtenir(db, commande_id).historique
