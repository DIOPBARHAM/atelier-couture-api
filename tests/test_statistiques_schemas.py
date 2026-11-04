from datetime import date

from pydantic import ValidationError
import pytest

from app.schemas.statistiques import (
    Granularite,
    PointChiffreAffaires,
    StatType,
    TableauDeBord,
    TopClient,
    TriClients,
)


def test_statistics_enums_expose_expected_values() -> None:
    assert [value.value for value in Granularite] == ["jour", "mois"]
    assert [value.value for value in TriClients] == [
        "chiffre_affaires",
        "commandes",
    ]


def test_dashboard_schema_accepts_expected_shape() -> None:
    dashboard = TableauDeBord(
        mois="2026-11",
        chiffre_affaires=100000,
        encaisse=60000,
        nb_commandes=3,
        reste_a_encaisser=40000,
        commandes_par_statut={"en_attente": 1, "terminee": 2},
        commandes_en_retard=1,
        commandes_pretes=2,
        livraisons_du_jour=1,
    )

    assert dashboard.model_dump()["mois"] == "2026-11"
    assert dashboard.commandes_par_statut["terminee"] == 2


def test_statistics_data_schemas_accept_expected_shapes() -> None:
    revenue = PointChiffreAffaires(
        periode="2026-11-04",
        chiffre_affaires=75000,
        encaisse=50000,
        nb_commandes=2,
    )
    garment = StatType(
        type_vetement_id=1,
        nom="Boubou",
        quantite=3,
        chiffre_affaires=105000,
    )
    client = TopClient(
        client_id=1,
        nom="Diop",
        prenom="Fatou",
        telephone="771234567",
        nb_commandes=2,
        chiffre_affaires=75000,
    )

    assert revenue.periode == "2026-11-04"
    assert garment.quantite == 3
    assert client.telephone == "771234567"


def test_statistics_schemas_reject_missing_required_fields() -> None:
    with pytest.raises(ValidationError):
        TableauDeBord(mois="2026-11")
    with pytest.raises(ValidationError):
        PointChiffreAffaires(
            periode=date(2026, 11, 4),
            chiffre_affaires=1,
        )
