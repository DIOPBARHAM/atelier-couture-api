from pydantic import BaseModel, ConfigDict, Field


class TypeVetementCreation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nom: str = Field(min_length=1, max_length=100)
    description: str | None = None
    prix_base: int = Field(ge=0)
    delai_jours: int = Field(ge=0)


class TypeVetementModification(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nom: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    prix_base: int | None = Field(default=None, ge=0)
    delai_jours: int | None = Field(default=None, ge=0)
    actif: bool | None = None


class TypeVetementLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    description: str | None
    prix_base: int
    delai_jours: int
    actif: bool
