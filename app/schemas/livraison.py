from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ModeLivraison, StatutLivraison


class LivraisonPlanification(BaseModel):
    mode: ModeLivraison
    adresse: str | None = Field(default=None, max_length=255)
    livreur: str | None = Field(default=None, max_length=100)
    date_prevue: date | None = None
    notes: str | None = None


class LivraisonConfirmation(BaseModel):
    autoriser_solde_impaye: bool = False


class LivraisonLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    commande_id: int
    mode: ModeLivraison
    adresse: str | None
    livreur: str | None
    date_prevue: date | None
    date_effective: date | None
    statut: StatutLivraison
    notes: str | None
