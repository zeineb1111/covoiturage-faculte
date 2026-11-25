"""Tests de l'inscription et de la connexion (BF1, BF2, BNF1)."""
from app.extensions import db
from app.models import Faculte, Utilisateur


def inscrire(client, email="amine@isi.tn", mot_de_passe="motdepasse123", faculte_id=1):
    return client.post("/inscription", data={
        "nom": "Ben Ali", "prenom": "Amine", "email": email, "faculte_id": faculte_id,
        "telephone": "20123456", "mot_de_passe": mot_de_passe,
    }, follow_redirects=True)


def test_inscription_reussie(client):
    reponse = inscrire(client)
    assert "Compte créé avec succès".encode() in reponse.data
    assert Utilisateur.query.filter_by(email="amine@isi.tn").first() is not None


def test_mot_de_passe_jamais_stocke_en_clair(client):
    """BNF1 : seule l'empreinte du mot de passe est enregistrée."""
    inscrire(client, mot_de_passe="motdepasse123")
    utilisateur = Utilisateur.query.filter_by(email="amine@isi.tn").first()
    assert utilisateur.mot_de_passe_hache != "motdepasse123"
    assert utilisateur.verifier_mot_de_passe("motdepasse123")


def test_inscription_refusee_si_email_deja_utilise(client):
    inscrire(client)
    reponse = inscrire(client)
    assert "existe déjà".encode() in reponse.data
    assert Utilisateur.query.count() == 1


def test_inscription_refusee_si_mot_de_passe_trop_court(client):
    reponse = inscrire(client, mot_de_passe="court")
    assert "au moins 8 caractères".encode() in reponse.data
    assert Utilisateur.query.count() == 0


def test_connexion_reussie_puis_deconnexion(client):
    inscrire(client)
    reponse = client.post("/connexion", data={
        "email": "amine@isi.tn", "mot_de_passe": "motdepasse123"}, follow_redirects=True)
    assert b"Mon profil (Amine)" in reponse.data
    reponse = client.get("/deconnexion", follow_redirects=True)
    assert "Vous êtes déconnecté".encode() in reponse.data


def test_connexion_refusee_si_mauvais_mot_de_passe(client):
    inscrire(client)
    reponse = client.post("/connexion", data={
        "email": "amine@isi.tn", "mot_de_passe": "mauvais"}, follow_redirects=True)
    assert "incorrect".encode() in reponse.data


def test_connexion_refusee_si_compte_suspendu(client):
    inscrire(client)
    utilisateur = Utilisateur.query.filter_by(email="amine@isi.tn").first()
    utilisateur.statut_compte = "suspendu"
    db.session.commit()
    reponse = client.post("/connexion", data={
        "email": "amine@isi.tn", "mot_de_passe": "motdepasse123"}, follow_redirects=True)
    assert "suspendu".encode() in reponse.data


def test_facultes_par_defaut_disponibles(client):
    """Plusieurs facultés sont proposées : l'application n'est pas réservée à l'ISI."""
    assert Faculte.query.count() >= 2
    reponse = client.get("/inscription")
    assert b"ISI" in reponse.data and b"FST" in reponse.data


def test_inscription_enregistre_la_faculte(client):
    inscrire(client, email="sara@fst.tn", faculte_id=2)
    utilisateur = Utilisateur.query.filter_by(email="sara@fst.tn").first()
    assert utilisateur.faculte.sigle == "FST"


def test_inscription_refusee_sans_faculte_valide(client):
    reponse = inscrire(client, faculte_id=9999)
    assert "choisir votre faculté".encode() in reponse.data
    assert Utilisateur.query.count() == 0
