from datetime import date
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.mesure import CHAMPS_MESURES

Cm = Annotated[float, Field(gt=0, le=300)]


class ChampsMesures(BaseModel):
    taille_cm: Cm | None = None
    tour_cou: Cm | None = None
    carrure_dos: Cm | None = None
    longueur_epaule: Cm | None = None
    tour_poitrine: Cm | None = None
    tour_taille: Cm | None = None
    tour_bassin: Cm | None = None
    longueur_manche: Cm | None = None
    tour_bras: Cm | None = None
    tour_poignet: Cm | None = None
    longueur_dos: Cm | None = None
    longueur_haut: Cm | None = None
    longueur_pantalon: Cm | None = None
    tour_cuisse: Cm | None = None
    tour_genou: Cm | None = None
    bas_pantalon: Cm | None = None
    entrejambe: Cm | None = None
    longueur_robe: Cm | None = None


class MesureCreation(ChampsMesures):
    date_prise: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def au_moins_une_mesure(self) -> Self:
        if all(getattr(self, champ) is None for champ in CHAMPS_MESURES):
            raise ValueError("Au moins une mesure doit être renseignée")
        return self


class MesureModification(ChampsMesures):
    date_prise: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def date_non_vidable(self) -> Self:
        if "date_prise" in self.model_fields_set and self.date_prise is None:
            raise ValueError("La date de prise ne peut pas être vidée")
        return self


class MesureLecture(ChampsMesures):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    date_prise: date
    prise_par_id: int
    notes: str | None
