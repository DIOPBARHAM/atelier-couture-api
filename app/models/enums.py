import enum


class Role(str, enum.Enum):
    admin = "admin"
    tailleur = "tailleur"
    accueil = "accueil"


class Genre(str, enum.Enum):
    homme = "homme"
    femme = "femme"
    enfant = "enfant"


class StatutCommande(str, enum.Enum):
    en_attente = "en_attente"
    en_coupe = "en_coupe"
    en_couture = "en_couture"
    essayage = "essayage"
    retouches = "retouches"
    terminee = "terminee"
    livree = "livree"
    annulee = "annulee"


class ModePaiement(str, enum.Enum):
    especes = "especes"
    wave = "wave"
    orange_money = "orange_money"
    virement = "virement"
    cheque = "cheque"


class ModeLivraison(str, enum.Enum):
    retrait_atelier = "retrait_atelier"
    domicile = "domicile"


class StatutLivraison(str, enum.Enum):
    planifiee = "planifiee"
    livree = "livree"
