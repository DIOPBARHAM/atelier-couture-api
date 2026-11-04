from datetime import date

from pydantic import BaseModel, ConfigDict

from app.models.enums import ModeLivraison, StatutLivraison


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
