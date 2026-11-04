import re

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.exceptions import Conflit, NonTrouve
from app.models import Client, Commande, Mesure
from app.models.enums import Genre, StatutCommande
from app.schemas.client import ClientCreation, ClientModification


def _telephone_existe(
    db: Session, telephone: str, sauf_id: int | None = None
) -> bool:
    stmt = select(Client.id).where(Client.telephone == telephone)
    if sauf_id is not None:
        stmt = stmt.where(Client.id != sauf_id)
    return db.scalar(stmt) is not None


def creer(db: Session, donnees: ClientCreation) -> Client:
    if _telephone_existe(db, donnees.telephone):
        raise Conflit("Un client existe déjà avec ce numéro de téléphone")
    client = Client(**donnees.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def obtenir(db: Session, client_id: int) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise NonTrouve("Client introuvable")
    return client


def lister(
    db: Session,
    q: str | None,
    genre: Genre | None,
    limit: int,
    offset: int,
) -> dict[str, object]:
    conditions = []
    if q:
        motif = f"%{q.strip()}%"
        chiffres = re.sub(r"[\s.\-()]", "", q)
        filtres = [Client.nom.ilike(motif), Client.prenom.ilike(motif)]
        if chiffres:
            filtres.append(Client.telephone.ilike(f"%{chiffres}%"))
        conditions.append(or_(*filtres))
    if genre is not None:
        conditions.append(Client.genre == genre)

    total = db.scalar(select(func.count()).select_from(Client).where(*conditions))
    items = db.scalars(
        select(Client)
        .where(*conditions)
        .order_by(Client.nom, Client.prenom)
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "items": list(items),
        "total": int(total or 0),
        "limit": limit,
        "offset": offset,
    }


def modifier(
    db: Session,
    client_id: int,
    donnees: ClientModification,
) -> Client:
    client = obtenir(db, client_id)
    changements = donnees.model_dump(exclude_unset=True)
    nouveau_tel = changements.get("telephone")
    if (
        nouveau_tel is not None
        and _telephone_existe(db, nouveau_tel, sauf_id=client.id)
    ):
        raise Conflit("Un client existe déjà avec ce numéro de téléphone")
    for champ, valeur in changements.items():
        setattr(client, champ, valeur)
    db.commit()
    db.refresh(client)
    return client


def supprimer(db: Session, client_id: int) -> None:
    client = obtenir(db, client_id)
    nb_commandes = db.scalar(
        select(func.count(Commande.id)).where(Commande.client_id == client_id)
    )
    if nb_commandes:
        raise Conflit("Suppression impossible : ce client a des commandes")
    db.delete(client)
    db.commit()


def commandes_du_client(
    db: Session, client_id: int, limit: int, offset: int
) -> dict[str, object]:
    obtenir(db, client_id)
    conditions = (Commande.client_id == client_id,)
    total = db.scalar(select(func.count(Commande.id)).where(*conditions))
    items = db.scalars(
        select(Commande)
        .where(*conditions)
        .order_by(Commande.date_commande.desc(), Commande.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "items": list(items),
        "total": int(total or 0),
        "limit": limit,
        "offset": offset,
    }


def resume(db: Session, client_id: int) -> dict[str, object]:
    obtenir(db, client_id)
    commandes_valides = (
        Commande.client_id == client_id,
        Commande.statut != StatutCommande.annulee,
    )
    nb, chiffre_affaires, total_paye, derniere_commande = db.execute(
        select(
            func.count(Commande.id),
            func.coalesce(func.sum(Commande.montant_total), 0),
            func.coalesce(func.sum(Commande.montant_paye), 0),
            func.max(Commande.date_commande),
        ).where(*commandes_valides)
    ).one()
    nb_mesures = db.scalar(
        select(func.count(Mesure.id)).where(Mesure.client_id == client_id)
    )
    chiffre_affaires = int(chiffre_affaires)
    total_paye = int(total_paye)
    return {
        "nb_commandes": nb,
        "chiffre_affaires": chiffre_affaires,
        "total_paye": total_paye,
        "solde_du": chiffre_affaires - total_paye,
        "derniere_commande": derniere_commande,
        "a_des_mesures": nb_mesures > 0,
    }
