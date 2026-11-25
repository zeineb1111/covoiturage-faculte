"""Configuration de l'application Covoiturage Faculté.

Deux configurations :
- Config : utilisée en développement et en production ;
- TestConfig : utilisée par les tests (base en mémoire, rien n'est conservé).

La base de données se choisit avec la variable d'environnement DATABASE_URL.
Par défaut, on utilise SQLite (aucune installation nécessaire). Pour utiliser
MySQL, il suffit de définir par exemple :
    mysql+pymysql://utilisateur:motdepasse@localhost/covoiturage
"""
import os


class Config:
    # Clé secrète qui protège les sessions. En production, la définir dans l'environnement.
    SECRET_KEY = os.environ.get("SECRET_KEY", "cle-de-developpement-a-changer")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///covoiturage.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False  # les tests envoient des formulaires sans jeton CSRF
