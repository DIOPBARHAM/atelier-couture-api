from datetime import date

from pydantic import BaseModel, ConfigDict

from app.models.enums import StatutCommande


class CommandeResume(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: str
    client_id: int
    statut: StatutCommande
    date_commande: date
    date_livraison_prevue: date
    montant_total: int
    montant_paye: int
    solde: int
