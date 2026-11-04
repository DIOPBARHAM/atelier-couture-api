from datetime import date

import pytest
from pydantic import ValidationError

from app.models.enums import Genre, StatutCommande
from app.schemas.catalogue import (
    TypeVetementCreation,
    TypeVetementModification,
)
from app.schemas.client import ClientCreation, ClientModification
from app.schemas.commande import CommandeResume
from app.schemas.commun import Page


def test_client_creation_normalizes_phone_and_strips_text() -> None:
    client = ClientCreation(
        nom="  Diallo ",
        prenom=" Awa ",
        telephone="(+221) 77-123.45 67",
        genre=Genre.femme,
    )

    assert client.nom == "Diallo"
    assert client.prenom == "Awa"
    assert client.telephone == "+221771234567"


@pytest.mark.parametrize(
    "telephone",
    ["12345", "123456789012345678901", "77abc123", "++221771234567"],
)
def test_client_creation_rejects_invalid_phone(telephone: str) -> None:
    with pytest.raises(ValidationError):
        ClientCreation(
            nom="Diallo",
            prenom="Awa",
            telephone=telephone,
            genre=Genre.femme,
        )


def test_client_modification_allows_omitted_optional_fields() -> None:
    assert ClientModification().model_dump(exclude_unset=True) == {}
    assert ClientModification(telephone="77 123 45 67").telephone == "771234567"


@pytest.mark.parametrize("field", ["nom", "prenom", "telephone", "genre"])
def test_client_modification_rejects_clearing_required_fields(field: str) -> None:
    with pytest.raises(ValidationError, match="ne peut pas être vidé"):
        ClientModification(**{field: None})


@pytest.mark.parametrize(
    "payload",
    [
        {"nom": " "},
        {"nom": "x" * 101},
        {"adresse": "x" * 256},
        {"email": "not-an-email"},
    ],
)
def test_client_modification_validates_values(payload: dict) -> None:
    with pytest.raises(ValidationError):
        ClientModification(**payload)


def test_catalogue_schemas_strip_names_and_validate_nonnegative_values() -> None:
    garment = TypeVetementCreation(
        nom="  Robe ",
        prix_base=0,
        delai_jours=0,
    )

    assert garment.nom == "Robe"
    with pytest.raises(ValidationError):
        TypeVetementCreation(nom="Robe", prix_base=-1, delai_jours=2)
    with pytest.raises(ValidationError):
        TypeVetementModification(prix_base=-1)


def test_generic_page_and_order_summary_schemas() -> None:
    page = Page[TypeVetementCreation](
        items=[TypeVetementCreation(nom="Chemise", prix_base=10, delai_jours=2)],
        total=1,
        limit=20,
        offset=0,
    )
    order = CommandeResume(
        id=1,
        numero="CMD-0001",
        client_id=3,
        statut=StatutCommande.en_attente,
        date_commande=date(2026, 1, 1),
        date_livraison_prevue=date(2026, 1, 10),
        montant_total=100,
        montant_paye=30,
        solde=70,
        en_retard=False,
    )

    assert page.total == len(page.items) == 1
    assert order.solde == 70
