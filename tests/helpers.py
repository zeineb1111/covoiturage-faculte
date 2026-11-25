"""Fonctions d'aide pour préparer des données de test."""
from datetime import date, datetime, time, timedelta

from app.extensions import db
from app.models import Faculte, Trajet, Utilisateur

MOT_DE_PASSE = "motdepasse123"


def creer_utilisateur(email, prenom="Test", nom="Utilisateur", faculte_id=1, admin=False):
    utilisateur = Utilisateur(nom=nom, prenom=prenom, email=email, faculte_id=None if admin else faculte_id,
                              est_admin=admin)
    utilisateur.definir_mot_de_passe(MOT_DE_PASSE)
    db.session.add(utilisateur)
    db.session.commit()
    return utilisateur


def connecter(client, email):
    return client.post("/connexion", data={"email": email, "mot_de_passe": MOT_DE_PASSE}, follow_redirects=True)


def creer_trajet(conducteur, places=2, jours=1, heure=time(8, 0), faculte_id=1, zone="El Mourouj", prix=2.0):
    """Crée un trajet directement en base (jours négatif = trajet déjà passé)."""
    trajet = Trajet(conducteur=conducteur, faculte_id=faculte_id, zone_depart=zone,
                    date_depart=date.today() + timedelta(days=jours), heure_depart=heure,
                    places_total=places, prix=prix)
    db.session.add(trajet)
    db.session.commit()
    return trajet


def donnees_trajet(jours=2, **modifs):
    """Données de formulaire valides pour publier un trajet."""
    donnees = {"faculte_id": 1, "zone_depart": "Radès",
               "date_depart": (date.today() + timedelta(days=jours)).isoformat(),
               "heure_depart": "08:30", "places_total": 3, "prix": "2,5"}
    donnees.update(modifs)
    return donnees
