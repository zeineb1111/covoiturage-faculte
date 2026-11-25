"""Création de l'application Flask (patron « application factory »)."""
from flask import Flask, render_template

from config import Config
from .extensions import csrf, db, login_manager


def create_app(config_class=Config):
    """Construit et configure l'application.

    Utiliser une fonction (au lieu d'une variable globale) permet de créer
    une application différente pour les tests, avec sa propre base de données.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Rattachement des extensions à l'application
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Enregistrement des blueprints (groupes de routes)
    from .auth.routes import auth_bp
    from .trajets.routes import trajets_bp
    from .reservations.routes import reservations_bp
    from .admin.routes import admin_bp
    from .avis.routes import avis_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(trajets_bp)
    app.register_blueprint(reservations_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(avis_bp)

    from .commandes import enregistrer_commandes
    enregistrer_commandes(app)

    @app.route("/")
    def accueil():
        return render_template("index.html")

    # Création des tables à partir des modèles si elles n'existent pas encore
    with app.app_context():
        from . import models  # noqa: F401  (importe les modèles pour que SQLAlchemy les connaisse)
        db.create_all()
        ajouter_facultes_par_defaut()

    return app


def ajouter_facultes_par_defaut():
    """Remplit la liste des facultés au premier lancement.

    Ce sont des exemples : l'administrateur pourra en ajouter d'autres,
    pour que n'importe quelle faculté puisse utiliser l'application.
    """
    from .models import Faculte

    if Faculte.query.count() == 0:
        exemples = [
            ("Institut Supérieur d'Informatique", "ISI", "Tunis"),
            ("Faculté des Sciences de Tunis", "FST", "Tunis"),
            ("École Nationale d'Ingénieurs de Tunis", "ENIT", "Tunis"),
            ("Faculté des Sciences Économiques et de Gestion de Tunis", "FSEGT", "Tunis"),
        ]
        for nom, sigle, ville in exemples:
            db.session.add(Faculte(nom=nom, sigle=sigle, ville=ville))
        db.session.commit()
