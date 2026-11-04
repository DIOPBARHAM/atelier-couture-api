from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Utilisateur
from app.schemas.auth import Token
from app.schemas.utilisateur import UtilisateurLecture
from app.security import creer_access_token
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post("/login", response_model=Token)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    utilisateur = auth_service.authentifier(db, form.username, form.password)
    if utilisateur is None:
        raise HTTPException(
            status_code=401,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_in = creer_access_token(utilisateur.id)
    return Token(access_token=token, token_type="bearer", expires_in=expires_in)


@router.get("/me", response_model=UtilisateurLecture)
def me(
    utilisateur: Utilisateur = Depends(get_current_user),
) -> Utilisateur:
    return utilisateur
