from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import exiger_roles
from app.models.enums import Role
from app.schemas.commande import CommandeResume
from app.schemas.statistiques import (
    Granularite,
    PointChiffreAffaires,
    StatType,
    TableauDeBord,
    TopClient,
    TriClients,
)
from app.services import statistique_service

router = APIRouter(
    prefix="/statistiques",
    tags=["Statistiques"],
    dependencies=[Depends(exiger_roles(Role.admin))],
)


@router.get("/tableau-de-bord", response_model=TableauDeBord)
def tableau_de_bord(db: Session = Depends(get_db)) -> TableauDeBord:
    return statistique_service.tableau_de_bord(db)


@router.get(
    "/chiffre-affaires",
    response_model=list[PointChiffreAffaires],
)
def chiffre_affaires(
    date_debut: date,
    date_fin: date,
    granularite: Granularite = Granularite.jour,
    db: Session = Depends(get_db),
) -> list[PointChiffreAffaires]:
    return statistique_service.chiffre_affaires(
        db, date_debut, date_fin, granularite
    )


@router.get("/types-vetement", response_model=list[StatType])
def types_vetement(db: Session = Depends(get_db)) -> list[StatType]:
    return statistique_service.par_type_vetement(db)


@router.get("/top-clients", response_model=list[TopClient])
def top_clients(
    limite: int = Query(default=10, ge=1, le=100),
    tri: TriClients = TriClients.chiffre_affaires,
    db: Session = Depends(get_db),
) -> list[TopClient]:
    return statistique_service.top_clients(db, limite, tri)


@router.get("/impayes", response_model=list[CommandeResume])
def impayes(db: Session = Depends(get_db)) -> list[CommandeResume]:
    return statistique_service.impayes(db)
