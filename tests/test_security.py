import jwt
import pytest

from app.config import settings
from app.security import (
    creer_access_token,
    decoder_access_token,
    hasher_mot_de_passe,
    verifier_mot_de_passe,
)


def test_password_hash_verifies_only_matching_password() -> None:
    password_hash = hasher_mot_de_passe("correct-password")

    assert password_hash != "correct-password"
    assert verifier_mot_de_passe("correct-password", password_hash)
    assert not verifier_mot_de_passe("wrong-password", password_hash)
    assert not verifier_mot_de_passe("password", "not-a-valid-hash")


def test_access_token_contains_user_id_and_expiration(monkeypatch) -> None:
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-for-unit-tests-32-bytes")
    monkeypatch.setattr(settings, "algorithm", "HS256")
    monkeypatch.setattr(settings, "access_token_expire_minutes", 10)

    token, expires_in = creer_access_token(42)
    payload = decoder_access_token(token)

    assert expires_in == 600
    assert payload["sub"] == "42"
    assert isinstance(payload["exp"], int)


def test_decoder_rejects_token_signed_with_another_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-for-unit-tests-32-bytes")
    token = jwt.encode(
        {"sub": "42"}, "another-test-secret-key-for-unit-tests-32-bytes", algorithm="HS256"
    )

    with pytest.raises(jwt.InvalidTokenError):
        decoder_access_token(token)
