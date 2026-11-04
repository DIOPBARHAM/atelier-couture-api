import pytest

from app.validation import traduire_erreur


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ({"type": "missing", "msg": "Field required"}, "champ obligatoire"),
        (
            {"type": "too_short", "ctx": {"min_length": 1}},
            "doit contenir au moins 1 élément(s)",
        ),
        (
            {
                "type": "string_too_short",
                "msg": "String should have at least 8 characters",
                "ctx": {"min_length": 8},
            },
            "doit contenir au moins 8 caractère(s)",
        ),
        (
            {
                "type": "string_too_long",
                "ctx": {"max_length": 12},
                "msg": "String should have at most 12 characters",
            },
            "doit contenir au plus 12 caractères",
        ),
        (
            {"type": "int_parsing", "msg": "Input should be a valid integer"},
            "doit être un nombre valide",
        ),
        (
            {"type": "enum", "ctx": {"expected": "admin, tailleur"}},
            "valeur invalide, valeurs possibles : admin, tailleur",
        ),
        (
            {"type": "value_error", "msg": "Value error, invalid email"},
            "adresse email invalide",
        ),
        (
            {"type": "value_error", "msg": "Value error, valeur invalide"},
            "valeur invalide",
        ),
    ],
)
def test_traduire_erreur(error: dict, expected: str) -> None:
    assert traduire_erreur(error) == expected
