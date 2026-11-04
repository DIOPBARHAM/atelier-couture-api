from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import TypeVetement, Utilisateur
from app.models.enums import Role
from app.security import hasher_mot_de_passe

CATALOGUE = [
    ("Boubou", "Boubou homme en bazin ou brodé", 35000, 10),
    ("Costume 2 pièces", "Veste et pantalon", 85000, 14),
    ("Robe", "Robe sur mesure", 30000, 7),
    ("Ensemble wax", "Tenue deux pièces en wax", 25000, 7),
    ("Chemise", "Chemise sur mesure", 15000, 5),
    ("Pantalon", "Pantalon sur mesure", 12000, 4),
    ("Retouche", "Ourlet, rétrécissement, remplacement de fermeture", 3000, 2),
]


def run() -> None:
    with SessionLocal() as db:
        email = settings.admin_email.strip().lower()
        if db.scalar(select(Utilisateur).where(Utilisateur.email == email)) is None:
            db.add(
                Utilisateur(
                    email=email,
                    nom_complet="Administrateur",
                    mot_de_passe_hash=hasher_mot_de_passe(settings.admin_password),
                    role=Role.admin,
                    actif=True,
                )
            )
            print(f"Compte admin créé : {email}")
        else:
            print("Compte admin déjà présent.")

        for nom, description, prix, delai in CATALOGUE:
            if db.scalar(select(TypeVetement).where(TypeVetement.nom == nom)) is None:
                db.add(
                    TypeVetement(
                        nom=nom,
                        description=description,
                        prix_base=prix,
                        delai_jours=delai,
                        actif=True,
                    )
                )
                print(f"Prestation ajoutée : {nom}")
        db.commit()


if __name__ == "__main__":  # pragma: no cover
    run()
