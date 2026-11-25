"""Tests du profil (BF3) et de la sécurité (CSRF, accès aux pages protégées)."""
from app import create_app
from app.extensions import db
from config import TestConfig
from tests.helpers import MOT_DE_PASSE, connecter, creer_utilisateur


def test_modifier_son_profil(client):
    utilisateur = creer_utilisateur("moi@isi.tn", prenom="Ancien", nom="Nom")
    connecter(client, "moi@isi.tn")
    reponse = client.post("/profil", data={"nom": "Nouveau", "prenom": "Prenom", "telephone": "20999888",
                                           "faculte_id": 2}, follow_redirects=True)
    assert "Profil mis à jour".encode() in reponse.data
    db.session.refresh(utilisateur)
    assert (utilisateur.nom, utilisateur.prenom, utilisateur.faculte_id) == ("Nouveau", "Prenom", 2)


def test_changer_son_mot_de_passe(client):
    utilisateur = creer_utilisateur("moi@isi.tn")
    connecter(client, "moi@isi.tn")
    donnees = {"nom": "N", "prenom": "P", "faculte_id": 1}
    # Mauvais ancien mot de passe
    reponse = client.post("/profil", data={**donnees, "ancien_mot_de_passe": "faux",
                                           "nouveau_mot_de_passe": "nouveaumdp123"}, follow_redirects=True)
    assert "ancien mot de passe est incorrect".encode() in reponse.data
    # Nouveau mot de passe trop court
    reponse = client.post("/profil", data={**donnees, "ancien_mot_de_passe": MOT_DE_PASSE,
                                           "nouveau_mot_de_passe": "court"}, follow_redirects=True)
    assert "au moins 8 caractères".encode() in reponse.data
    # Changement valide
    client.post("/profil", data={**donnees, "ancien_mot_de_passe": MOT_DE_PASSE,
                                 "nouveau_mot_de_passe": "nouveaumdp123"}, follow_redirects=True)
    db.session.refresh(utilisateur)
    assert utilisateur.verifier_mot_de_passe("nouveaumdp123")


def test_profil_exige_une_connexion(client):
    reponse = client.get("/profil")
    assert reponse.status_code == 302 and "/connexion" in reponse.headers["Location"]


def test_pages_protegees_redirigent_vers_la_connexion(client):
    for url in ("/mes-trajets", "/mes-reservations", "/trajets/nouveau", "/profil"):
        reponse = client.get(url)
        assert reponse.status_code == 302 and "/connexion" in reponse.headers["Location"], url


def test_pages_publiques_accessibles(client):
    for url in ("/", "/trajets", "/connexion", "/inscription"):
        assert client.get(url).status_code == 200, url


def test_protection_csrf_active_en_configuration_reelle():
    """Sans jeton CSRF, un formulaire POST est rejeté (BNF2/BNF3)."""
    class ConfigAvecCsrf(TestConfig):
        WTF_CSRF_ENABLED = True

    app = create_app(ConfigAvecCsrf)
    client = app.test_client()
    reponse = client.post("/inscription", data={"nom": "A", "prenom": "B", "email": "a@b.tn",
                                                "mot_de_passe": "motdepasse123", "faculte_id": 1})
    assert reponse.status_code == 400
