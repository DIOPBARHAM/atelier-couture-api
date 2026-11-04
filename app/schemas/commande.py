from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import StatutCommande
from app.schemas.livraison import LivraisonLecture
from app.schemas.paiement import PaiementLecture


class LigneCreation(BaseModel):
    type_vetement_id: int
    description: str | None = Field(default=None, max_length=255)
    quantite: int = Field(ge=1)
    prix_unitaire: int | None = Field(default=None, ge=0)


class CommandeCreation(BaseModel):
    client_id: int
    mesure_id: int | None = None
    date_commande: date | None = None
    date_livraison_prevue: date | None = None
    remise: int = Field(default=0, ge=0)
    notes: str | None = None
    lignes: list[LigneCreation] = Field(min_length=1)


class CommandeModification(BaseModel):
    mesure_id: int | None = None
    date_livraison_prevue: date | None = None
    remise: int | None = Field(default=None, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def champs_non_vidables(self) -> Self:
        for champ in ("date_livraison_prevue", "remise"):
            if champ in self.model_fields_set and getattr(self, champ) is None:
                raise ValueError(f"Le champ {champ} ne peut pas être vidé")
        return self


class LigneLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type_vetement_id: int
    description: str | None
    quantite: int
    prix_unitaire: int
    sous_total: int


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
    en_retard: bool


class CommandeDetail(CommandeResume):
    mesure_id: int | None
    date_livraison_reelle: date | None
    remise: int
    notes: str | None
    cree_par_id: int
    created_at: datetime
    updated_at: datetime
    lignes: list[LigneLecture]
    paiements: list[PaiementLecture]
    livraison: LivraisonLecture | None


class StatutChangement(BaseModel):
    statut: StatutCommande
    commentaire: str | None = Field(default=None, max_length=500)


class HistoriqueLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ancien_statut: StatutCommande | None
    nouveau_statut: StatutCommande
    commentaire: str | None
    utilisateur_id: int
    date_changement: datetime
