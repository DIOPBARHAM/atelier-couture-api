from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.enums import Role
from app.schemas.auth import Token
from app.schemas.utilisateur import (
    UtilisateurCreation,
    UtilisateurLecture,
    UtilisateurModification,
)


def test_token_defaults_to_bearer() -> None:
    token = Token(access_token="signed-token", expires_in=3600)

    assert token.token_type == "bearer"


def test_user_creation_validates_email_password_and_role() -> None:
    user = UtilisateurCreation(
        email="tailleur@example.com",
        nom_complet="Awa Diallo",
        mot_de_passe="long-enough-password",
        role=Role.tailleur,
    )

    assert user.role is Role.tailleur
    with pytest.raises(ValidationError):
        UtilisateurCreation(
            email="not-an-email",
            nom_complet="Awa Diallo",
            mot_de_passe="short",
            role=Role.tailleur,
        )


def test_user_modification_fields_are_optional() -> None:
    assert UtilisateurModification().model_dump(exclude_unset=True) == {}
    assert UtilisateurModification(actif=False).actif is False


def test_user_read_schema_loads_model_attributes_without_password() -> None:
    class User:
        id = 1
        email = "tailleur@example.com"
        nom_complet = "Awa Diallo"
        role = Role.tailleur
        actif = True
        created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mot_de_passe_hash = "never serialize"

    user = UtilisateurLecture.model_validate(User())

    assert user.id == 1
    assert user.role is Role.tailleur
    assert "mot_de_passe_hash" not in user.model_dump()
