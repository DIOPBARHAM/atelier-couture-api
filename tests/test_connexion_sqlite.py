from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Utilisateur
from app.models.enums import Role
from app.security import hasher_mot_de_passe

P = "/api/v1"
EMAIL = "fatou.accueil@example.com"
MOT_DE_PASSE = "Secret1234"


@pytest.fixture
def connexion() -> Iterator[tuple[TestClient, Session, Utilisateur]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)

    utilisateur = Utilisateur(
        email=EMAIL,
        nom_complet="Accueil Test",
        mot_de_passe_hash=hasher_mot_de_passe(MOT_DE_PASSE),
        role=Role.accueil,
        actif=True,
    )
    session.add(utilisateur)
    session.commit()

    def get_test_db() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = get_test_db
    client = TestClient(app)
    try:
        yield client, session, utilisateur
    finally:
        app.dependency_overrides.clear()
        client.close()
        session.close()
        engine.dispose()


def _se_connecter(client: TestClient, email: str, mot_de_passe: str):
    return client.post(
        f"{P}/auth/login",
        data={"username": email, "password": mot_de_passe},
    )


def test_connexion_reussie_puis_acces_au_profil(connexion) -> None:
    client, _, _ = connexion

    reponse = _se_connecter(client, EMAIL, MOT_DE_PASSE)
    assert reponse.status_code == 200
    jeton = reponse.json()
    assert jeton["token_type"] == "bearer"
    assert jeton["expires_in"] > 0

    profil = client.get(
        f"{P}/auth/me",
        headers={"Authorization": f"Bearer {jeton['access_token']}"},
    )
    assert profil.status_code == 200
    assert profil.json()["email"] == EMAIL
    assert "mot_de_passe_hash" not in profil.json()


def test_connexion_insensible_a_la_casse_de_l_email(connexion) -> None:
    client, _, _ = connexion
    assert _se_connecter(client, EMAIL.upper(), MOT_DE_PASSE).status_code == 200


def test_echec_de_connexion_message_identique(connexion) -> None:
    client, _, _ = connexion

    mauvais_mot_de_passe = _se_connecter(client, EMAIL, "mauvais-mot-de-passe")
    email_inconnu = _se_connecter(
        client,
        "inconnu@example.com",
        MOT_DE_PASSE,
    )

    assert mauvais_mot_de_passe.status_code == 401
    assert email_inconnu.status_code == 401
    assert mauvais_mot_de_passe.json() == email_inconnu.json()


def test_compte_desactive_refuse_meme_avec_un_jeton_valide(connexion) -> None:
    client, session, utilisateur = connexion

    jeton = _se_connecter(client, EMAIL, MOT_DE_PASSE).json()["access_token"]
    entetes = {"Authorization": f"Bearer {jeton}"}
    assert client.get(f"{P}/auth/me", headers=entetes).status_code == 200

    utilisateur.actif = False
    session.commit()

    assert client.get(f"{P}/auth/me", headers=entetes).status_code == 401
    assert _se_connecter(client, EMAIL, MOT_DE_PASSE).status_code == 401


def test_acces_sans_jeton_refuse(connexion) -> None:
    client, _, _ = connexion
    assert client.get(f"{P}/auth/me").status_code == 401
