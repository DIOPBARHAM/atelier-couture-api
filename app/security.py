from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import settings

_hasher = PasswordHasher()


def hasher_mot_de_passe(mot_de_passe: str) -> str:
    return _hasher.hash(mot_de_passe)


def verifier_mot_de_passe(mot_de_passe: str, hash_stocke: str) -> bool:
    try:
        return _hasher.verify(hash_stocke, mot_de_passe)
    except (VerificationError, InvalidHashError):
        return False


def creer_access_token(user_id: int) -> tuple[str, int]:
    """Retourne (jeton, durée de validité en secondes)."""
    expires_in = settings.access_token_expire_minutes * 60
    exp = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    token = jwt.encode(
        {"sub": str(user_id), "exp": exp},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return token, expires_in


def decoder_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
