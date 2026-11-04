from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import Conflit, DonneesInvalides, NonTrouve
from app.models import (
    Client,
    Commande,
    HistoriqueStatut,
    LigneCommande,
    Mesure,
    TypeVetement,
    Utilisateur,
)
from app.models.enums import Role, StatutCommande
from app.schemas.commande import (
    CommandeCreation,
    CommandeModification,
    LigneCreation,
    StatutChangement,
)

STATUTS_FINAUX = (StatutCommande.livree, StatutCommande.annulee)

TRANSITIONS: dict[StatutCommande, set[StatutCommande]] = {
    StatutCommande.en_attente: {StatutCommande.en_coupe, StatutCommande.annulee},
    StatutCommande.en_coupe: {StatutCommande.en_couture, StatutCommande.annulee},
    StatutCommande.en_couture: {
        StatutCommande.essayage,
        StatutCommande.terminee,
        StatutCommande.annulee,
    },
    StatutCommande.essayage: {
        StatutCommande.retouches,
        StatutCommande.terminee,
        StatutCommande.annulee,
    },
    StatutCommande.retouches: {
        StatutCommande.essayage,
        StatutCommande.terminee,
        StatutCommande.annulee,
    },
    StatutCommande.terminee: {StatutCommande.livree},
    StatutCommande.livree: set(),
    StatutCommande.annulee: set(),
}


def _numero_suivant(db: Session, annee: int) -> str:
    """RG5 : génère une numérotation continue par année."""
    prefixe = f"CMD-{annee}-"
    dernier = db.scalar(
        select(func.max(Commande.numero)).where(
            Commande.numero.like(f"{prefixe}%")
        )
    )
    suivant = int(dernier.rsplit("-", 1)[1]) + 1 if dernier else 1
    return f"{prefixe}{suivant:05d}"


def _total_brut(lignes: list[LigneCommande]) -> int:
    return sum(ligne.quantite * ligne.prix_unitaire for ligne in lignes)


def _recalculer(commande: Commande) -> None:
    """RG7 : les montants sont calculés par le serveur."""
    commande.montant_total = _total_brut(commande.lignes) - commande.remise
    commande.montant_paye = sum(paiement.montant for paiement in commande.paiements)


def _construire_ligne(
    db: Session, donnees: LigneCreation
) -> tuple[LigneCommande, TypeVetement]:
    prestation = db.get(TypeVetement, donnees.type_vetement_id)
    if prestation is None:
        raise NonTrouve(f"Prestation introuvable (id {donnees.type_vetement_id})")
    if not prestation.actif:
        raise DonneesInvalides(
            f"La prestation « {prestation.nom} » est désactivée et ne peut pas être commandée"
        )
    prix = (
        donnees.prix_unitaire
        if donnees.prix_unitaire is not None
        else prestation.prix_base
    )
    ligne = LigneCommande(
        type_vetement_id=prestation.id,
        description=donnees.description,
        quantite=donnees.quantite,
        prix_unitaire=prix,
    )
    return ligne, prestation


def _verifier_mesure(db: Session, mesure_id: int, client_id: int) -> None:
    """RG9 : la mesure doit appartenir au client de la commande."""
    mesure = db.get(Mesure, mesure_id)
    if mesure is None or mesure.client_id != client_id:
        raise DonneesInvalides(
            "La mesure indiquée n'existe pas ou n'appartient pas à ce client"
        )


def _verifier_modifiable(commande: Commande) -> None:
    """RG12 : une commande livrée ou annulée n'est plus modifiable."""
    if commande.statut in STATUTS_FINAUX:
        raise Conflit(f"Commande {commande.statut.value} : modification impossible")


def creer(
    db: Session, donnees: CommandeCreation, acteur: Utilisateur
) -> Commande:
    client = db.get(Client, donnees.client_id)
    if client is None:
        raise NonTrouve("Client introuvable")

    lignes: list[LigneCommande] = []
    delais: list[int] = []
    for ligne_donnees in donnees.lignes:
        ligne, prestation = _construire_ligne(db, ligne_donnees)
        lignes.append(ligne)
        delais.append(prestation.delai_jours)

    brut = _total_brut(lignes)
    if donnees.remise > brut:
        raise DonneesInvalides(
            "La remise ne peut pas dépasser le total brut de la commande"
        )

    date_commande = donnees.date_commande or date.today()
    if donnees.date_livraison_prevue is not None:
        if donnees.date_livraison_prevue < date_commande:
            raise DonneesInvalides(
                "La date de livraison prévue ne peut pas précéder la date de commande"
            )
        date_prevue = donnees.date_livraison_prevue
    else:
        date_prevue = date_commande + timedelta(days=max(delais))

    if donnees.mesure_id is not None:
        _verifier_mesure(db, donnees.mesure_id, client.id)
        mesure_id = donnees.mesure_id
    else:
        derniere = db.scalar(
            select(Mesure)
            .where(Mesure.client_id == client.id)
            .order_by(Mesure.date_prise.desc(), Mesure.id.desc())
            .limit(1)
        )
        mesure_id = derniere.id if derniere else None

    commande = Commande(
        numero=_numero_suivant(db, date_commande.year),
        client_id=client.id,
        mesure_id=mesure_id,
        statut=StatutCommande.en_attente,
        date_commande=date_commande,
        date_livraison_prevue=date_prevue,
        remise=donnees.remise,
        montant_total=brut - donnees.remise,
        montant_paye=0,
        notes=donnees.notes,
        cree_par_id=acteur.id,
    )
    commande.lignes = lignes
    commande.historique.append(
        HistoriqueStatut(
            ancien_statut=None,
            nouveau_statut=StatutCommande.en_attente,
            commentaire="Création de la commande",
            utilisateur_id=acteur.id,
        )
    )
    db.add(commande)
    db.commit()
    db.refresh(commande)
    return commande


def obtenir(db: Session, commande_id: int) -> Commande:
    commande = db.get(Commande, commande_id)
    if commande is None:
        raise NonTrouve("Commande introuvable")
    return commande


def lister(
    db: Session,
    statut: StatutCommande | None,
    client_id: int | None,
    en_retard: bool | None,
    date_min: date | None,
    date_max: date | None,
    numero: str | None,
    limit: int,
    offset: int,
) -> dict[str, object]:
    conditions = []
    if statut is not None:
        conditions.append(Commande.statut == statut)
    if client_id is not None:
        conditions.append(Commande.client_id == client_id)
    if numero:
        conditions.append(Commande.numero.ilike(f"%{numero.strip()}%"))
    if date_min is not None:
        conditions.append(Commande.date_commande >= date_min)
    if date_max is not None:
        conditions.append(Commande.date_commande <= date_max)
    if en_retard is not None:
        critere = (Commande.date_livraison_prevue < date.today()) & (
            Commande.statut.not_in(STATUTS_FINAUX)
        )
        conditions.append(critere if en_retard else ~critere)

    total = db.scalar(
        select(func.count()).select_from(Commande).where(*conditions)
    )
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


def modifier(
    db: Session,
    commande_id: int,
    donnees: CommandeModification,
) -> Commande:
    commande = obtenir(db, commande_id)
    _verifier_modifiable(commande)
    changements = donnees.model_dump(exclude_unset=True)

    if "mesure_id" in changements and changements["mesure_id"] is not None:
        _verifier_mesure(db, changements["mesure_id"], commande.client_id)

    if "date_livraison_prevue" in changements:
        if changements["date_livraison_prevue"] < commande.date_commande:
            raise DonneesInvalides(
                "La date de livraison prévue ne peut pas précéder la date de commande"
            )

    if "remise" in changements:
        brut = _total_brut(commande.lignes)
        if changements["remise"] > brut:
            raise DonneesInvalides(
                "La remise ne peut pas dépasser le total brut de la commande"
            )
        nouveau_total = brut - changements["remise"]
        montant_paye = sum(paiement.montant for paiement in commande.paiements)
        if nouveau_total < montant_paye:
            raise Conflit(
                f"Le nouveau total ({nouveau_total} FCFA) ne peut pas être inférieur "
                f"au montant déjà payé ({montant_paye} FCFA)"
            )

    for champ, valeur in changements.items():
        setattr(commande, champ, valeur)
    _recalculer(commande)
    db.commit()
    db.refresh(commande)
    return commande


def ajouter_ligne(
    db: Session, commande_id: int, donnees: LigneCreation
) -> Commande:
    commande = obtenir(db, commande_id)
    if commande.statut != StatutCommande.en_attente:
        raise Conflit("Les lignes ne sont modifiables que pour une commande en attente")
    ligne, _ = _construire_ligne(db, donnees)
    commande.lignes.append(ligne)
    _recalculer(commande)
    db.commit()
    db.refresh(commande)
    return commande


def supprimer_ligne(
    db: Session, commande_id: int, ligne_id: int
) -> Commande:
    commande = obtenir(db, commande_id)
    if commande.statut != StatutCommande.en_attente:
        raise Conflit("Les lignes ne sont modifiables que pour une commande en attente")
    ligne = next((item for item in commande.lignes if item.id == ligne_id), None)
    if ligne is None:
        raise NonTrouve("Ligne de commande introuvable")
    if len(commande.lignes) == 1:
        raise Conflit("Une commande doit conserver au moins une ligne")

    nouveau_brut = _total_brut(commande.lignes) - ligne.quantite * ligne.prix_unitaire
    if commande.remise > nouveau_brut:
        raise Conflit(
            "Suppression impossible : la remise dépasserait le total brut. "
            "Réduisez d'abord la remise"
        )
    montant_paye = sum(paiement.montant for paiement in commande.paiements)
    if nouveau_brut - commande.remise < montant_paye:
        raise Conflit(
            "Suppression impossible : le total passerait sous le montant déjà payé"
        )

    commande.lignes.remove(ligne)
    _recalculer(commande)
    db.commit()
    db.refresh(commande)
    return commande
