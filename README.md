# API Atelier de Couture

API REST de gestion d'un atelier de couture : clients, mesures, catalogue de prestations, commandes, paiements, livraisons et statistiques.

**Stack** : Python 3.12, FastAPI, PostgreSQL 16, SQLAlchemy 2, Alembic, Pydantic, JWT (Argon2 pour les mots de passe), pytest, Docker.

## Architecture

- `app/routers/` : routes par domaine (authentification, vérification des rôles, validation des réponses). Aucune règle métier.
- `app/services/` : toute la logique métier (calculs de solde, transitions de statut, livraisons).
- `app/models/` et `app/schemas/` : modèles SQLAlchemy et schémas Pydantic distincts (création, modification, lecture). Aucun modèle n'est renvoyé directement, le hash du mot de passe ne sort jamais.
- `alembic/` : migrations (aucun `create_all`).
- `tests/` : tests unitaires et d'intégration.

## Démarrage avec Docker (recommandé)

Prérequis : Docker et Docker Compose.

```bash
cp .env.example .env
# éditer .env : changer SECRET_KEY et les mots de passe
docker compose up --build
```

Au démarrage, le conteneur de l'API attend PostgreSQL, applique `alembic upgrade head`, exécute le seed (compte admin et catalogue de départ), puis lance l'API.

- Documentation interactive (Swagger) : http://localhost:8000/docs
- Santé de l'API et de la base : http://localhost:8000/health

Pour tout arrêter : `docker compose down` (ajouter `-v` pour supprimer aussi les données).

> Le mot de passe PostgreSQL ne doit pas contenir de caractères spéciaux (`@`, `/`, `:`), car il est placé tel quel dans l'URL de connexion.

## Installation locale (sans Docker pour l'API)

```bash
python -m venv .venv
source .venv/Scripts/activate        # Git Bash sous Windows ; Linux/macOS : source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d db              # PostgreSQL seul
alembic upgrade head
python -m app.seed
fastapi dev app/main.py
```

## Variables d'environnement (`.env`)

| Variable | Rôle |
| :--- | :--- |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Identifiants de la base PostgreSQL |
| `DATABASE_URL` | URL de connexion pour un lancement local (avec `localhost`). Docker Compose la recompose avec l'hôte `db` |
| `SECRET_KEY` | Clé de signature des jetons JWT. Générer avec `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Durée de validité d'un jeton (60 par défaut) |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Compte administrateur créé par le seed |

Le fichier `.env` n'est jamais versionné.

## Comptes de test

Le seed crée le compte **admin** à partir de `ADMIN_EMAIL` et `ADMIN_PASSWORD` (avec `.env.example` : `admin@atelier.sn` / `change_me`).

Les comptes `accueil` et `tailleur` se créent depuis `/docs` : se connecter en admin (bouton **Authorize**), puis `POST /api/v1/utilisateurs` avec :

```json
{"email": "accueil@atelier.sn", "nom_complet": "Awa Accueil", "mot_de_passe": "Accueil123", "role": "accueil"}
```

```json
{"email": "tailleur@atelier.sn", "nom_complet": "Moussa Tailleur", "mot_de_passe": "Tailleur123", "role": "tailleur"}
```

Dans Swagger, **Authorize** demande `username` (l'adresse email) et `password`.

## Rôles

| Rôle | Droits |
| :--- | :--- |
| `admin` | Comptes utilisateurs, catalogue, suppression de client, annulation de paiement, statistiques |
| `accueil` | Clients, commandes, paiements, livraisons, annulation de commande |
| `tailleur` | Saisie et correction des mesures, changement des statuts de production (pas d'annulation) |
| Utilisateur connecté | Lecture sur clients, mesures, catalogue, commandes, livraisons |

## Format des réponses

- Erreurs : `{"detail": "message explicite en français"}`. Codes : 401 (non authentifié ou compte désactivé), 403 (rôle insuffisant), 404, 409 (conflit métier), 422 (données invalides).
- Pagination : `{"items": [...], "total": n, "limit": n, "offset": n}` (`limit` 20 par défaut, 100 au maximum).
- Montants en entiers (FCFA), mesures en centimètres.

## Workflow des commandes

`en_attente` → `en_coupe` → `en_couture` → `essayage` ⇄ `retouches` → `terminee` → `livree`

- `annulee` est possible depuis tout statut sauf `terminee`, `livree` et `annulee`.
- `terminee` → `livree` se fait uniquement par `POST /commandes/{id}/livraison/confirmer`.
- `livree` et `annulee` sont des statuts finaux.

## Routes

Toutes les routes sont préfixées par `/api/v1`, sauf `/health`.

### Authentification et utilisateurs

| Méthode | Chemin | Accès | Rôle de la route |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/login` | Public | Connexion (formulaire OAuth2), renvoie le jeton |
| `GET` | `/auth/me` | Connecté | Profil de l'utilisateur connecté |
| `POST` | `/utilisateurs` | Admin | Crée un compte |
| `GET` | `/utilisateurs` | Admin | Liste des comptes |
| `GET` | `/utilisateurs/{id}` | Admin | Détail d'un compte |
| `PATCH` | `/utilisateurs/{id}` | Admin | Modifie nom, rôle, état, mot de passe |

### Clients et catalogue

| Méthode | Chemin | Accès | Rôle de la route |
| :--- | :--- | :--- | :--- |
| `POST` | `/clients` | Connecté | Crée un client |
| `GET` | `/clients` | Connecté | Recherche paginée (`q`, `genre`, `limit`, `offset`) |
| `GET` | `/clients/{id}` | Connecté | Fiche client |
| `PATCH` | `/clients/{id}` | Connecté | Modification partielle |
| `DELETE` | `/clients/{id}` | Admin | Supprime un client sans commande |
| `GET` | `/clients/{id}/commandes` | Connecté | Commandes du client |
| `GET` | `/clients/{id}/resume` | Connecté | Synthèse (commandes, CA, solde dû) |
| `POST` | `/catalogue` | Admin | Ajoute une prestation |
| `GET` | `/catalogue` | Connecté | Prestations actives |
| `GET` | `/catalogue/{id}` | Connecté | Détail d'une prestation |
| `PATCH` | `/catalogue/{id}` | Admin | Modifie ou désactive une prestation |

### Mesures

| Méthode | Chemin | Accès | Rôle de la route |
| :--- | :--- | :--- | :--- |
| `POST` | `/clients/{id}/mesures` | Tailleur | Saisit une prise de mesures |
| `GET` | `/clients/{id}/mesures` | Connecté | Historique des mesures |
| `GET` | `/clients/{id}/mesures/derniere` | Connecté | Dernière prise de mesures |
| `GET` | `/mesures/{id}` | Connecté | Détail d'une prise |
| `PATCH` | `/mesures/{id}` | Tailleur | Corrige une prise |
| `DELETE` | `/mesures/{id}` | Tailleur | Supprime une prise non utilisée |

### Commandes

| Méthode | Chemin | Accès | Rôle de la route |
| :--- | :--- | :--- | :--- |
| `POST` | `/commandes` | Accueil | Crée une commande (numéro `CMD-AAAA-NNNNN`, calculs serveur) |
| `GET` | `/commandes` | Connecté | Liste paginée et filtrée |
| `GET` | `/commandes/{id}` | Connecté | Détail (lignes, paiements, livraison, solde, retard) |
| `PATCH` | `/commandes/{id}` | Accueil | Modifie mesure, date prévue, remise, notes |
| `POST` | `/commandes/{id}/statut` | Connecté | Change le statut selon le workflow |
| `GET` | `/commandes/{id}/historique` | Connecté | Historique des statuts |
| `POST` | `/commandes/{id}/lignes` | Accueil | Ajoute une ligne (commande `en_attente`) |
| `DELETE` | `/commandes/{id}/lignes/{ligne_id}` | Accueil | Supprime une ligne (commande `en_attente`) |

### Paiements, livraisons et statistiques

| Méthode | Chemin | Accès | Rôle de la route |
| :--- | :--- | :--- | :--- |
| `POST` | `/commandes/{id}/paiements` | Accueil | Enregistre un paiement |
| `GET` | `/commandes/{id}/paiements` | Connecté | Liste des paiements |
| `DELETE` | `/paiements/{id}` | Admin | Annule un paiement |
| `PUT` | `/commandes/{id}/livraison` | Accueil | Planifie ou replanifie la livraison |
| `GET` | `/commandes/{id}/livraison` | Connecté | Détail de la livraison |
| `POST` | `/commandes/{id}/livraison/confirmer` | Accueil | Confirme la livraison |
| `GET` | `/livraisons` | Connecté | Tournée triée par date prévue |
| `GET` | `/statistiques/tableau-de-bord` | Admin | Indicateurs du mois courant |
| `GET` | `/statistiques/chiffre-affaires` | Admin | CA et encaissements par jour ou par mois |
| `GET` | `/statistiques/types-vetement` | Admin | Quantités et CA par prestation |
| `GET` | `/statistiques/top-clients` | Admin | Meilleurs clients |
| `GET` | `/statistiques/impayes` | Admin | Commandes impayées |
| `GET` | `/health` (hors `/api/v1`) | Public | Santé de l'API et de la base |

## Tests

```bash
pytest -q                                   # tous les tests
pytest --cov=app --cov-report=term-missing  # avec la couverture
docker compose exec api pytest -q           # dans le conteneur
```

Les tests utilisent SQLite en mémoire. `tests/test_scenario_demo.py` déroule le scénario de démonstration complet.

## Scénario de démonstration

1. `accueil` crée Fatou Diop (`77 123 45 67`) ; un doublon `771234567` renvoie 409.
2. `tailleur` saisit ses mesures ; `accueil` essayant la même chose reçoit 403.
3. `accueil` crée une commande (2 boubous, 1 pantalon négocié, remise) : numéro, total et date prévue calculés.
4. Passage direct à `terminee` : 409 avec la liste des statuts possibles.
5. `tailleur` fait avancer le statut jusqu'à `terminee`, avec un aller-retour `essayage` / `retouches`.
6. `accueil` encaisse un acompte Wave ; un paiement supérieur au solde renvoie 409.
7. Confirmation de livraison avec solde non nul : 409.
8. Encaissement du solde puis confirmation : statut `livree`, solde 0.
9. `admin` consulte le tableau de bord ; `accueil` y accède : 403.
10. `admin` consulte les impayés et les commandes en retard.
