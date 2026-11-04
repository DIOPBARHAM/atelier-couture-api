from datetime import date
from enum import Enum

from pydantic import BaseModel


class Granularite(str, Enum):
    jour = "jour"
    mois = "mois"


class TriClients(str, Enum):
    chiffre_affaires = "chiffre_affaires"
    commandes = "commandes"


class TableauDeBord(BaseModel):
    mois: str
    chiffre_affaires: int
    encaisse: int
    nb_commandes: int
    reste_a_encaisser: int
    commandes_par_statut: dict[str, int]
    commandes_en_retard: int
    commandes_pretes: int
    livraisons_du_jour: int


class PointChiffreAffaires(BaseModel):
    periode: str
    chiffre_affaires: int
    encaisse: int
    nb_commandes: int


class StatType(BaseModel):
    type_vetement_id: int
    nom: str
    quantite: int
    chiffre_affaires: int


class TopClient(BaseModel):
    client_id: int
    nom: str
    prenom: str
    telephone: str
    nb_commandes: int
    chiffre_affaires: int
