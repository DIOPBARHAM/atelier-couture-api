from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import DonneesInvalides
from app.models import Client, Commande, LigneCommande, Livraison, Paiement, TypeVetement
from app.models.enums import StatutCommande, StatutLivraison
from app.schemas.statistiques import Granularite, TriClients

NON_ANNULEE = Commande.statut != StatutCommande.annulee
STATUTS_FINAUX = (StatutCommande.livree, StatutCommande.annulee)


def _bornes_du_mois(jour: date) -> tuple[date, date]:
    """Retourne le premier jour du mois inclus et du mois suivant exclu."""
    debut = jour.replace(day=1)
    fin = (debut + timedelta(days=32)).replace(day=1)
    return debut, fin


def tableau_de_bord(db: Session) -> dict[str, object]:
    aujourdhui = date.today()
    debut, fin = _bornes_du_mois(aujourdhui)

    chiffre_affaires, nb_commandes = db.execute(
        select(
            func.coalesce(func.sum(Commande.montant_total), 0),
            func.count(Commande.id),
        ).where(
            NON_ANNULEE,
            Commande.date_commande >= debut,
            Commande.date_commande < fin,
        )
    ).one()
    encaisse = db.scalar(
        select(func.coalesce(func.sum(Paiement.montant), 0)).where(
            Paiement.date_paiement >= debut,
            Paiement.date_paiement < fin,
        )
    )
    reste = db.scalar(
        select(
            func.coalesce(
                func.sum(Commande.montant_total - Commande.montant_paye), 0
            )
        ).where(NON_ANNULEE)
    )

    par_statut = {statut.value: 0 for statut in StatutCommande}
    for statut, nombre in db.execute(
        select(Commande.statut, func.count(Commande.id)).group_by(Commande.statut)
    ):
        par_statut[statut.value] = nombre

    en_retard = db.scalar(
        select(func.count(Commande.id)).where(
            Commande.date_livraison_prevue < aujourdhui,
            Commande.statut.not_in(STATUTS_FINAUX),
        )
    )
    livraisons_du_jour = db.scalar(
        select(func.count(Livraison.id)).where(
            Livraison.date_prevue == aujourdhui,
            Livraison.statut == StatutLivraison.planifiee,
        )
    )

    return {
        "mois": f"{aujourdhui.year}-{aujourdhui.month:02d}",
        "chiffre_affaires": int(chiffre_affaires),
        "encaisse": int(encaisse),
        "nb_commandes": nb_commandes,
        "reste_a_encaisser": int(reste),
        "commandes_par_statut": par_statut,
        "commandes_en_retard": en_retard,
        "commandes_pretes": par_statut[StatutCommande.terminee.value],
        "livraisons_du_jour": livraisons_du_jour,
    }


def chiffre_affaires(
    db: Session,
    date_debut: date,
    date_fin: date,
    granularite: Granularite,
) -> list[dict[str, object]]:
    if date_debut > date_fin:
        raise DonneesInvalides(
            "La date de début ne peut pas être postérieure à la date de fin"
        )

    def cle(jour: date) -> str:
        if granularite == Granularite.jour:
            return jour.isoformat()
        return f"{jour.year}-{jour.month:02d}"

    points: dict[str, dict[str, object]] = {}

    def point(periode: str) -> dict[str, object]:
        return points.setdefault(
            periode,
            {
                "periode": periode,
                "chiffre_affaires": 0,
                "encaisse": 0,
                "nb_commandes": 0,
            },
        )

    commandes = db.execute(
        select(
            Commande.date_commande,
            func.sum(Commande.montant_total),
            func.count(Commande.id),
        )
        .where(
            NON_ANNULEE,
            Commande.date_commande.between(date_debut, date_fin),
        )
        .group_by(Commande.date_commande)
    )
    for jour, total, nombre in commandes:
        periode = point(cle(jour))
        periode["chiffre_affaires"] += int(total)
        periode["nb_commandes"] += nombre

    paiements = db.execute(
        select(Paiement.date_paiement, func.sum(Paiement.montant))
        .where(Paiement.date_paiement.between(date_debut, date_fin))
        .group_by(Paiement.date_paiement)
    )
    for jour, total in paiements:
        point(cle(jour))["encaisse"] += int(total)

    return [points[periode] for periode in sorted(points)]


def par_type_vetement(db: Session) -> list[dict[str, object]]:
    quantite = func.sum(LigneCommande.quantite).label("quantite")
    chiffre = func.sum(
        LigneCommande.quantite * LigneCommande.prix_unitaire
    ).label("chiffre_affaires")
    lignes = db.execute(
        select(TypeVetement.id, TypeVetement.nom, quantite, chiffre)
        .join(LigneCommande, LigneCommande.type_vetement_id == TypeVetement.id)
        .join(Commande, Commande.id == LigneCommande.commande_id)
        .where(NON_ANNULEE)
        .group_by(TypeVetement.id, TypeVetement.nom)
        .order_by(chiffre.desc(), TypeVetement.nom)
    )
    return [
        {
            "type_vetement_id": identifiant,
            "nom": nom,
            "quantite": int(nombre),
            "chiffre_affaires": int(total),
        }
        for identifiant, nom, nombre, total in lignes
    ]


def top_clients(db: Session, limite: int, tri: TriClients) -> list[dict[str, object]]:
    nombre = func.count(Commande.id).label("nombre")
    chiffre = func.sum(Commande.montant_total).label("chiffre_affaires")
    critere = chiffre.desc() if tri == TriClients.chiffre_affaires else nombre.desc()
    lignes = db.execute(
        select(
            Client.id,
            Client.nom,
            Client.prenom,
            Client.telephone,
            nombre,
            chiffre,
        )
        .join(Commande, Commande.client_id == Client.id)
        .where(NON_ANNULEE)
        .group_by(Client.id, Client.nom, Client.prenom, Client.telephone)
        .order_by(critere, chiffre.desc(), Client.id)
        .limit(limite)
    )
    return [
        {
            "client_id": identifiant,
            "nom": nom,
            "prenom": prenom,
            "telephone": telephone,
            "nb_commandes": nombre_commandes,
            "chiffre_affaires": int(total),
        }
        for (
            identifiant,
            nom,
            prenom,
            telephone,
            nombre_commandes,
            total,
        ) in lignes
    ]


def impayes(db: Session) -> list[Commande]:
    """Commandes non annulées impayées, triées par échéance la plus proche."""
    return list(
        db.scalars(
            select(Commande)
            .where(
                NON_ANNULEE,
                Commande.montant_total > Commande.montant_paye,
            )
            .order_by(Commande.date_livraison_prevue, Commande.id)
        )
    )
