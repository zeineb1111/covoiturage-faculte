"""Tests de l'espace administrateur (BF13, BF14, BF15, BNF2)."""
from app.extensions import db
from app.models import Avis, Faculte, StatutReservation, StatutTrajet, Utilisateur
from app.services.reservations import accepter_reservation, demander_reservation
from tests.helpers import connecter, creer_trajet, creer_utilisateur


def connecter_admin(client):
    creer_utilisateur("admin@covoiturage.tn", admin=True)
    connecter(client, "admin@covoiturage.tn")


def test_pages_admin_interdites_aux_non_administrateurs(client):
    creer_utilisateur("etudiant@isi.tn")
    connecter(client, "etudiant@isi.tn")
    for url in ("/admin/", "/admin/utilisateurs", "/admin/facultes", "/admin/trajets", "/admin/avis"):
        assert client.get(url).status_code == 403, url


def test_pages_admin_exigent_une_connexion(client):
    reponse = client.get("/admin/")
    assert reponse.status_code == 302 and "/connexion" in reponse.headers["Location"]


def test_le_lien_administration_n_apparait_que_pour_un_admin(client):
    creer_utilisateur("etudiant@isi.tn")
    connecter(client, "etudiant@isi.tn")
    assert b"Administration" not in client.get("/").data
    client.get("/deconnexion")
    connecter_admin(client)
    assert b"Administration" in client.get("/").data


def test_tableau_de_bord(client):
    connecter_admin(client)
    reponse = client.get("/admin/")
    assert reponse.status_code == 200 and "Utilisateurs".encode() in reponse.data


def test_ajouter_une_faculte(client):
    connecter_admin(client)
    reponse = client.post("/admin/facultes", data={"nom": "Faculté de Médecine de Tunis", "sigle": "FMT",
                                                   "ville": "Tunis"}, follow_redirects=True)
    assert "ajoutée".encode() in reponse.data
    assert Faculte.query.filter_by(sigle="FMT").one().ville == "Tunis"
    # La nouvelle faculté est immédiatement proposée à l'inscription
    client.get("/deconnexion")
    assert b"FMT" in client.get("/inscription").data


def test_ajouter_une_faculte_refuse_les_doublons_et_les_noms_vides(client):
    connecter_admin(client)
    avant = Faculte.query.count()
    reponse = client.post("/admin/facultes", data={"nom": "faculté des sciences de tunis"}, follow_redirects=True)
    assert "existe déjà".encode() in reponse.data
    reponse = client.post("/admin/facultes", data={"nom": "   "}, follow_redirects=True)
    assert "obligatoire".encode() in reponse.data
    assert Faculte.query.count() == avant


def test_modifier_une_faculte(client):
    connecter_admin(client)
    reponse = client.post("/admin/facultes/1/modifier", data={"nom": "ISI Tunis", "sigle": "ISI", "ville": "Ariana"},
                          follow_redirects=True)
    assert "Faculté modifiée".encode() in reponse.data
    assert db.session.get(Faculte, 1).nom == "ISI Tunis"
    reponse = client.post("/admin/facultes/1/modifier", data={"nom": "Faculté des Sciences de Tunis"},
                          follow_redirects=True)
    assert "porte déjà ce nom".encode() in reponse.data


def test_suspendre_puis_reactiver_un_compte(client):
    etudiant = creer_utilisateur("etudiant@isi.tn")
    connecter_admin(client)
    client.post(f"/admin/utilisateurs/{etudiant.id}/statut")
    db.session.refresh(etudiant)
    assert etudiant.statut_compte == "suspendu"
    client.post(f"/admin/utilisateurs/{etudiant.id}/statut")
    db.session.refresh(etudiant)
    assert etudiant.statut_compte == "actif"


def test_un_administrateur_ne_peut_pas_etre_suspendu(client):
    connecter_admin(client)
    admin = Utilisateur.query.filter_by(est_admin=True).one()
    reponse = client.post(f"/admin/utilisateurs/{admin.id}/statut", follow_redirects=True)
    assert "ne peut pas être suspendu".encode() in reponse.data
    assert admin.statut_compte == "actif"


def test_un_compte_suspendu_ne_peut_plus_se_connecter(client):
    etudiant = creer_utilisateur("etudiant@isi.tn")
    connecter_admin(client)
    client.post(f"/admin/utilisateurs/{etudiant.id}/statut")
    client.get("/deconnexion")
    reponse = connecter(client, "etudiant@isi.tn")
    assert "suspendu".encode() in reponse.data


def test_retirer_un_trajet_annule_ses_reservations(client):
    cond, passager = creer_utilisateur("cond@isi.tn"), creer_utilisateur("p@isi.tn")
    trajet = creer_trajet(cond)
    reservation = accepter_reservation(demander_reservation(trajet, passager))
    connecter_admin(client)
    reponse = client.post(f"/admin/trajets/{trajet.id}/retirer", follow_redirects=True)
    assert "retiré".encode() in reponse.data
    db.session.refresh(trajet); db.session.refresh(reservation)
    assert trajet.statut == StatutTrajet.ANNULE and reservation.statut == StatutReservation.ANNULEE


def test_supprimer_un_avis_abusif(client):
    cond, passager = creer_utilisateur("cond@isi.tn"), creer_utilisateur("p@isi.tn")
    trajet = creer_trajet(cond)
    avis = Avis(note=1, commentaire="abusif", auteur=passager, destinataire=cond, trajet=trajet)
    db.session.add(avis)
    db.session.commit()
    connecter_admin(client)
    assert b"abusif" in client.get("/admin/avis").data
    client.post(f"/admin/avis/{avis.id}/supprimer")
    assert Avis.query.count() == 0


def test_commande_creer_admin(app):
    runner = app.test_cli_runner()
    resultat = runner.invoke(args=["creer-admin", "chef@covoiturage.tn", "motdepasse123"])
    assert "Administrateur créé" in resultat.output
    admin = Utilisateur.query.filter_by(email="chef@covoiturage.tn").one()
    assert admin.est_admin and admin.verifier_mot_de_passe("motdepasse123")
    # Refuse un mot de passe trop court et un e-mail déjà utilisé
    assert runner.invoke(args=["creer-admin", "autre@covoiturage.tn", "court"]).exit_code != 0
    assert runner.invoke(args=["creer-admin", "chef@covoiturage.tn", "motdepasse123"]).exit_code != 0


def test_commande_donnees_demo(app):
    runner = app.test_cli_runner()
    assert "Données de démonstration ajoutées" in runner.invoke(args=["donnees-demo"]).output
    assert Utilisateur.query.filter_by(email="conducteur@demo.tn").count() == 1
    assert "existent déjà" in runner.invoke(args=["donnees-demo"]).output
