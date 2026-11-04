from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import TypeVetement, Utilisateur
from app.models.enums import Role
from app.security import verifier_mot_de_passe
from app.seed import CATALOGUE, run


def test_seed_creates_admin_and_catalogue_idempotently(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr("app.seed.SessionLocal", lambda: Session(engine))
    monkeypatch.setattr("app.seed.settings.admin_email", "  ADMIN@example.com ")
    monkeypatch.setattr("app.seed.settings.admin_password", "test-admin-password")

    run()
    run()

    with Session(engine) as db:
        users = db.scalars(select(Utilisateur)).all()
        garments = db.scalars(select(TypeVetement)).all()

        assert len(users) == 1
        assert users[0].email == "admin@example.com"
        assert users[0].nom_complet == "Administrateur"
        assert users[0].role is Role.admin
        assert users[0].actif is True
        assert verifier_mot_de_passe("test-admin-password", users[0].mot_de_passe_hash)
        assert len(garments) == len(CATALOGUE)
        assert db.scalar(select(func.count()).select_from(TypeVetement)) == len(CATALOGUE)

    engine.dispose()
