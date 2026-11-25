# Covoiturage Faculté

Application web de covoiturage étudiant vers la faculté, utilisable par n'importe quelle faculté
(mini-projet Génie Logiciel et Données, L2-CS, 2026/2027).

Technologies : Python, Flask, SQLAlchemy, Flask-Login, Flask-WTF, Bootstrap, pytest.
Base de données : SQLite par défaut, MySQL possible (variable `DATABASE_URL`).

## Lancer le projet

```bash
# 1. Créer et activer un environnement virtuel
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux / macOS

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. (Facultatif) Créer un administrateur et des données de démonstration
python -m flask --app run creer-admin admin@covoiturage.tn admin12345
python -m flask --app run donnees-demo

# 4. Lancer l'application
python run.py
```

L'application est alors accessible sur http://127.0.0.1:5000

## Comptes de démonstration

| Rôle | E-mail | Mot de passe |
|---|---|---|
| Administrateur | admin@covoiturage.tn | admin12345 |
| Conducteur | conducteur@demo.tn | demo12345 |
| Passager | passager@demo.tn | demo12345 |

À ne pas utiliser en production : changez ces mots de passe.

## Lancer les tests

```bash
python -m pytest
```

## Fonctionnalités

| Réf. | Fonctionnalité | Page |
|---|---|---|
| BF1, BF2 | Inscription (avec choix de la faculté), connexion, déconnexion | `/inscription`, `/connexion` |
| BF3 | Consulter et modifier son profil, changer son mot de passe | `/profil` |
| BF4 | Publier un trajet | `/trajets/nouveau` |
| BF5 | Modifier ou annuler un trajet | `/trajets/<id>/modifier` |
| BF6 | Consulter les demandes de réservation de ses trajets | `/trajets/<id>` (conducteur) |
| BF7 | Accepter ou refuser une demande | `/trajets/<id>` (conducteur) |
| BF8 | Rechercher un trajet (faculté, zone, date) | `/trajets` |
| BF9, BF10 | Réserver une place, annuler sa réservation | `/trajets/<id>`, `/mes-reservations` |
| BF11 | Historique des réservations | `/mes-reservations` |
| BF12 | Noter un conducteur ou un passager après un trajet | `/trajets/<id>` |
| BF13 | Gérer les comptes (suspendre, réactiver) | `/admin/utilisateurs` |
| BF14 | Retirer un trajet, supprimer un avis abusif | `/admin/trajets`, `/admin/avis` |
| BF15 | Ajouter ou modifier une faculté | `/admin/facultes` |

## Règles de gestion

- RG01 : les réservations confirmées ne dépassent jamais le nombre de places d'un trajet ;
- RG02 : un passager ne peut pas réserver deux fois le même trajet ;
- RG03 : un conducteur ne peut pas réserver son propre trajet ;
- RG04 : on ne peut réserver que des trajets à venir ;
- un avis n'est possible qu'après le départ d'un trajet, entre participants (passager confirmé et conducteur).

## Organisation du code

| Dossier / fichier | Rôle |
|---|---|
| `run.py`, `config.py` | Démarrage et configuration |
| `app/__init__.py` | Création de l'application |
| `app/extensions.py` | Base de données, connexions, protection CSRF |
| `app/models.py` | Modèles : Faculté, Utilisateur, Trajet, Réservation, Avis |
| `app/auth/` | Inscription, connexion, profil |
| `app/trajets/` | Publier, rechercher, modifier, annuler, terminer un trajet |
| `app/reservations/` | Demander, accepter, refuser, annuler une réservation |
| `app/avis/` | Noter un participant |
| `app/admin/` | Espace administrateur |
| `app/services/` | Règles métier (réservations, avis), séparées des pages |
| `app/commandes.py` | Commandes `creer-admin` et `donnees-demo` |
| `app/templates/` | Pages HTML (Bootstrap) |
| `tests/` | Tests automatiques |

## Sécurité

- mots de passe stockés sous forme hachée (jamais en clair) ;
- protection CSRF sur tous les formulaires ;
- pages réservées protégées par connexion et par rôle (erreur 403 sinon) ;
- données validées côté serveur, requêtes SQL via SQLAlchemy (pas de SQL écrit à la main).
