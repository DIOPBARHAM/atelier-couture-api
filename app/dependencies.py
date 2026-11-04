import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Utilisateur
from app.models.enums import Role
from app.security import decoder_access_token

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login", auto_error=False
)


def _non_authentifie(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Utilisateur:
    if token is None:
        raise _non_authentifie(
            "Authentification requise : connectez-vous via /api/v1/auth/login"
        )
    try:
        user_id = int(decoder_access_token(token)["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise _non_authentifie(
            "Jeton invalide ou expiré : reconnectez-vous"
        ) from exc
    utilisateur = db.get(Utilisateur, user_id)
    if utilisateur is None or not utilisateur.actif:
        raise _non_authentifie("Compte désactivé ou inexistant")
    return utilisateur


def exiger_roles(*roles: Role):
    """Fabrique une dépendance qui n'autorise que les rôles listés."""

    def verifier(
        utilisateur: Utilisateur = Depends(get_current_user),
    ) -> Utilisateur:
        if utilisateur.role not in roles:
            raise HTTPException(
                status_code=403, detail="Droits insuffisants pour cette action"
            )
        return utilisateur

    return verifier
