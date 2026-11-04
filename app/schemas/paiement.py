from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ModePaiement


class PaiementCreation(BaseModel):
    montant: int = Field(gt=0)
    mode: ModePaiement
    reference: str | None = Field(default=None, max_length=100)
    date_paiement: date | None = None


class PaiementLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    commande_id: int
    montant: int
    mode: ModePaiement
    reference: str | None
    date_paiement: date
    enregistre_par_id: int
    created_at: datetime
