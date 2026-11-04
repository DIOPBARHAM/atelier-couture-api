from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.models.commande import Commande, LigneCommande
from app.models.enums import StatutCommande
from app.schemas.commande import (
    CommandeCreation,
    CommandeDetail,
    CommandeModification,
    CommandeResume,
    LigneCreation,
    LigneLecture,
)


def test_order_creation_requires_at_least_one_line() -> None:
    with pytest.raises(ValidationError) as error:
        CommandeCreation(client_id=1, lignes=[])

    assert error.value.errors()[0]["type"] == "too_short"


@pytest.mark.parametrize("quantity", [0, -1])
def test_order_line_requires_positive_quantity(quantity: int) -> None:
    with pytest.raises(ValidationError):
        LigneCreation(type_vetement_id=1, quantite=quantity)


def test_order_line_defaults_and_limits_price_fields() -> None:
    line = LigneCreation(type_vetement_id=2, quantite=3)

    assert line.prix_unitaire is None
    with pytest.raises(ValidationError):
        LigneCreation(
            type_vetement_id=2,
            quantite=1,
            prix_unitaire=-1,
        )


@pytest.mark.parametrize("field", ["date_livraison_prevue", "remise"])
def test_order_modification_does_not_allow_clearing_required_fields(
    field: str,
) -> None:
    with pytest.raises(ValidationError, match="ne peut pas être vidé"):
        CommandeModification(**{field: None})


def test_order_line_subtotal_property_is_included_in_read_schema() -> None:
    line = LigneCommande(
        id=1,
        type_vetement_id=2,
        description=None,
        quantite=3,
        prix_unitaire=12500,
    )

    assert line.sous_total == 37500
    assert LigneLecture.model_validate(line).sous_total == 37500


def test_order_is_late_only_if_open_and_past_due() -> None:
    base = {
        "id": 1,
        "numero": "CMD-0001",
        "client_id": 1,
        "date_commande": date.today(),
        "date_livraison_prevue": date.today() - timedelta(days=1),
        "montant_total": 100,
        "montant_paye": 0,
    }
    late = Commande(
        **base,
        statut=StatutCommande.en_couture,
    )
    delivered = Commande(
        **base,
        statut=StatutCommande.livree,
    )
    cancelled = Commande(
        **base,
        statut=StatutCommande.annulee,
    )
    not_due = Commande(
        **{**base, "date_livraison_prevue": date.today()},
        statut=StatutCommande.en_couture,
    )

    assert late.en_retard is True
    assert delivered.en_retard is False
    assert cancelled.en_retard is False
    assert not_due.en_retard is False
    assert CommandeResume.model_validate(late).en_retard is True


def test_full_order_detail_schema_includes_related_read_models() -> None:
    today = date.today()
    order = Commande(
        id=1,
        numero="CMD-0001",
        client_id=2,
        mesure_id=None,
        statut=StatutCommande.en_attente,
        date_commande=today,
        date_livraison_prevue=today,
        date_livraison_reelle=None,
        remise=0,
        montant_total=0,
        montant_paye=0,
        notes=None,
        cree_par_id=3,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        lignes=[],
        paiements=[],
        livraison=None,
    )

    detail = CommandeDetail.model_validate(order)

    assert detail.id == order.id
    assert detail.lignes == []
    assert detail.paiements == []
    assert detail.livraison is None
