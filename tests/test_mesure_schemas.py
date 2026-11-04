from datetime import date

import pytest
from pydantic import ValidationError

from app.models.mesure import CHAMPS_MESURES
from app.schemas.mesure import (
    ChampsMesures,
    MesureCreation,
    MesureLecture,
    MesureModification,
)


def test_measure_fields_match_model_and_accept_valid_range() -> None:
    assert set(ChampsMesures.model_fields) == set(CHAMPS_MESURES)

    measurement = MesureCreation(taille_cm=0.1, tour_cou=300)

    assert measurement.taille_cm == 0.1
    assert measurement.tour_cou == 300


@pytest.mark.parametrize("value", [0, -0.1, 300.1])
def test_measure_creation_rejects_values_outside_allowed_range(value: float) -> None:
    with pytest.raises(ValidationError):
        MesureCreation(taille_cm=value)


def test_measure_creation_requires_at_least_one_measurement() -> None:
    with pytest.raises(ValidationError, match="Au moins une mesure"):
        MesureCreation(notes="Aucune mesure")


def test_measure_modification_can_update_notes_without_measurements() -> None:
    modification = MesureModification(notes="Mise à jour")

    assert modification.model_dump(exclude_unset=True) == {"notes": "Mise à jour"}


def test_measure_modification_does_not_allow_clearing_date() -> None:
    with pytest.raises(ValidationError, match="date de prise ne peut pas être vidée"):
        MesureModification(date_prise=None)


def test_measure_modification_validates_measurement_range() -> None:
    with pytest.raises(ValidationError):
        MesureModification(longueur_robe=301)


def test_measure_read_model_is_orm_compatible() -> None:
    class Measurement:
        id = 1
        client_id = 2
        date_prise = date(2026, 11, 4)
        prise_par_id = 3
        notes = None
        taille_cm = 165

    result = MesureLecture.model_validate(Measurement())

    assert result.id == 1
    assert result.client_id == 2
    assert result.taille_cm == 165
