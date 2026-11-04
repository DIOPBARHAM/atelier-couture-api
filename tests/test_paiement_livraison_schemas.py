from datetime import date

import pytest
from pydantic import ValidationError

from app.models.enums import ModeLivraison, ModePaiement
from app.schemas.livraison import (
    LivraisonConfirmation,
    LivraisonPlanification,
)
from app.schemas.paiement import PaiementCreation


def test_payment_creation_requires_positive_amount_and_valid_mode() -> None:
    payment = PaiementCreation(montant=1, mode=ModePaiement.especes)

    assert payment.montant == 1
    assert payment.date_paiement is None
    assert payment.reference is None

    for amount in (0, -1):
        with pytest.raises(ValidationError):
            PaiementCreation(montant=amount, mode=ModePaiement.especes)


def test_payment_creation_limits_reference_and_accepts_explicit_date() -> None:
    payment = PaiementCreation(
        montant=5000,
        mode=ModePaiement.wave,
        reference="TX-123",
        date_paiement=date(2026, 11, 4),
    )

    assert payment.reference == "TX-123"
    assert payment.date_paiement == date(2026, 11, 4)
    with pytest.raises(ValidationError):
        PaiementCreation(
            montant=5000,
            mode=ModePaiement.wave,
            reference="x" * 101,
        )


def test_delivery_scheduling_defaults_and_limits_text_fields() -> None:
    delivery = LivraisonPlanification(mode=ModeLivraison.domicile)

    assert delivery.adresse is None
    assert delivery.livreur is None
    assert delivery.date_prevue is None
    assert delivery.notes is None

    with pytest.raises(ValidationError):
        LivraisonPlanification(
            mode=ModeLivraison.domicile,
            adresse="x" * 256,
        )
    with pytest.raises(ValidationError):
        LivraisonPlanification(
            mode=ModeLivraison.domicile,
            livreur="x" * 101,
        )


def test_delivery_confirmation_defaults_to_requiring_payment() -> None:
    assert LivraisonConfirmation().autoriser_solde_impaye is False
    assert (
        LivraisonConfirmation(autoriser_solde_impaye=True).autoriser_solde_impaye
        is True
    )
