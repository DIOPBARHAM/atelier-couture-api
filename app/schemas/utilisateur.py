from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Role


class UtilisateurCreation(BaseModel):
    email: EmailStr
    nom_complet: str = Field(min_length=1, max_length=150)
    mot_de_passe: str = Field(min_length=8, max_length=128)
    role: Role


class UtilisateurModification(BaseModel):
    nom_complet: str | None = Field(default=None, min_length=1, max_length=150)
    role: Role | None = None
    actif: bool | None = None
    mot_de_passe: str | None = Field(default=None, min_length=8, max_length=128)


class UtilisateurLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    nom_complet: str
    role: Role
    actif: bool
    created_at: datetime
