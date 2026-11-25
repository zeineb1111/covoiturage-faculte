"""Commandes utiles en ligne de commande (flask --app run <commande>).

- creer-admin : crée un compte administrateur ;
- donnees-demo : ajoute quelques comptes et trajets pour tester et faire la démonstration.
"""
from datetime import date, time, timedelta

import click

from .extensions import db
from .models import Faculte, Trajet, Utilisateur


def enregistrer_commandes(app):

    @app.cli.command("creer-admin")
    @click.argument("email")
    @click.argument("mot_de_passe")
    def creer_admin(email, mot_de_passe):
        """Crée un administrateur : flask --app run creer-admin EMAIL MOT_DE_PASSE"""
        email = email.strip().lower()
        if len(mot_de_passe) < 8:
            raise click.ClickException("Le mot de passe doit contenir au moins 8 caractères.")
        if Utilisateur.query.filter_by(email=email).first():
            raise click.ClickException("Un compte existe déjà avec cet e-mail.")
        admin = Utilisateur(nom="Admin", prenom="Plateforme", email=email, est_admin=True)
        admin.definir_mot_de_passe(mot_de_passe)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Administrateur créé : {email}")

    @app.cli.command("donnees-demo")
    def donnees_demo():
        """Ajoute des comptes et des trajets d'exemple (mot de passe : demo12345)."""
        if Utilisateur.query.filter_by(email="conducteur@demo.tn").first():
            click.echo("Les données de démonstration existent déjà.")
            return
        isi = Faculte.query.filter_by(sigle="ISI").first()
        fst = Faculte.query.filter_by(sigle="FST").first()
        conducteur = Utilisateur(nom="Ben Salah", prenom="Yassine", email="conducteur@demo.tn",
                                 telephone="20111222", faculte=isi)
        passager = Utilisateur(nom="Trabelsi", prenom="Sarra", email="passager@demo.tn",
                               telephone="20333444", faculte=isi)
        for u in (conducteur, passager):
            u.definir_mot_de_passe("demo12345")
            db.session.add(u)
        demain = date.today() + timedelta(days=1)
        db.session.add_all([
            Trajet(conducteur=conducteur, faculte=isi, zone_depart="El Mourouj", date_depart=demain,
                   heure_depart=time(7, 45), places_total=3, prix=2.0),
            Trajet(conducteur=conducteur, faculte=isi, zone_depart="Radès", date_depart=demain,
                   heure_depart=time(8, 15), places_total=2, prix=1.5),
            Trajet(conducteur=conducteur, faculte=fst, zone_depart="Sokra", date_depart=demain + timedelta(days=1),
                   heure_depart=time(8, 0), places_total=4, prix=2.5),
        ])
        db.session.commit()
        click.echo("Données de démonstration ajoutées : conducteur@demo.tn et passager@demo.tn (mot de passe demo12345).")
