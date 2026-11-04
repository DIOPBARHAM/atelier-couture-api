import re
from datetime import date, datetime
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models.enums import Genre

_TEL_RE = re.compile(r"^\+?\d{6,20}$")


def normaliser_telephone(valeur: str) -> str:
    """RG1 : retire espaces, points, tirets, parenthèses puis valide."""
    nettoye = re.sub(r"[\s.\-()]", "", valeur)
    if not _TEL_RE.match(nettoye):
        raise ValueError(
            "Téléphone invalide : 6 à 20 chiffres, avec un + initial facultatif"
        )
    return nettoye


class ClientCreation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nom: str = Field(min_length=1, max_length=100)
    prenom: str = Field(min_length=1, max_length=100)
    telephone: str
    email: EmailStr | None = None
    adresse: str | None = Field(default=None, max_length=255)
    genre: Genre
    notes: str | None = None

    @field_validator("telephone")
    @classmethod
    def valider_telephone(cls, valeur: str) -> str:
        return normaliser_telephone(valeur)


class ClientModification(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nom: str | None = Field(default=None, min_length=1, max_length=100)
    prenom: str | None = Field(default=None, min_length=1, max_length=100)
    telephone: str | None = None
    email: EmailStr | None = None
    adresse: str | None = Field(default=None, max_length=255)
    genre: Genre | None = None
    notes: str | None = None

    @field_validator("telephone")
    @classmethod
    def valider_telephone(cls, valeur: str | None) -> str | None:
        return None if valeur is None else normaliser_telephone(valeur)

    @model_validator(mode="after")
    def champs_non_vidables(self) -> Self:
        for champ in ("nom", "prenom", "telephone", "genre"):
            if champ in self.model_fields_set and getattr(self, champ) is None:
                raise ValueError(f"Le champ {champ} ne peut pas être vidé")
        return self


class ClientLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    prenom: str
    telephone: str
    email: str | None
    adresse: str | None
    genre: Genre
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ClientResume(BaseModel):
    nb_commandes: int
    chiffre_affaires: int
    total_paye: int
    solde_du: int
    derniere_commande: date | None
    a_des_mesures: bool
