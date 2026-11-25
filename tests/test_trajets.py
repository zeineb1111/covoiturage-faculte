"""Tests des trajets : publier, rechercher, modifier, annuler (BF4, BF5, BF8)."""
from app.models import StatutReservation, StatutTrajet, Trajet
from app.services.reservations import accepter_reservation, demander_reservation
from tests.helpers import connecter, creer_trajet, creer_utilisateur, donnees_trajet


def test_publier_un_trajet(client):
    creer_utilisateur("cond@isi.tn")
    connecter(client, "cond@isi.tn")
    reponse = client.post("/trajets/nouveau", data=donnees_trajet(), follow_redirects=True)
    assert "Trajet publié avec succès".encode() in reponse.data
    trajet = Trajet.query.one()
    assert trajet.prix == 2.5 and trajet.places_total == 3 and trajet.conducteur.email == "cond@isi.tn"


def test_publier_exige_une_connexion(client):
    reponse = client.get("/trajets/nouveau")
    assert reponse.status_code == 302 and "/connexion" in reponse.headers["Location"]


def test_publier_refuse_une_date_passee(client):
    creer_utilisateur("cond@isi.tn")
    connecter(client, "cond@isi.tn")
    reponse = client.post("/trajets/nouveau", data=donnees_trajet(jours=-1), follow_redirects=True)
    assert "dans le futur".encode() in reponse.data and Trajet.query.count() == 0


def test_publier_refuse_un_nombre_de_places_invalide(client):
    creer_utilisateur("cond@isi.tn")
    connecter(client, "cond@isi.tn")
    for places in ("0", "9", "abc"):
        reponse = client.post("/trajets/nouveau", data=donnees_trajet(places_total=places), follow_redirects=True)
        assert "entre 1 et 8".encode() in reponse.data
    assert Trajet.query.count() == 0


def test_publier_refuse_un_prix_negatif(client):
    creer_utilisateur("cond@isi.tn")
    connecter(client, "cond@isi.tn")
    reponse = client.post("/trajets/nouveau", data=donnees_trajet(prix="-1"), follow_redirects=True)
    assert "prix doit être".encode() in reponse.data and Trajet.query.count() == 0


def test_recherche_filtre_par_faculte_zone_et_date(client):
    cond = creer_utilisateur("cond@isi.tn")
    creer_trajet(cond, zone="Ariana", faculte_id=1)
    creer_trajet(cond, zone="Sokra", faculte_id=2)
    # Tous les trajets
    assert b"Ariana" in client.get("/trajets").data
    # Par faculté de destination : seul le trajet vers la FST (id 2) apparaît
    reponse = client.get("/trajets?faculte_id=2")
    assert b"Sokra" in reponse.data and b"Ariana" not in reponse.data
    # Par zone (recherche partielle, sans tenir compte des majuscules)
    reponse = client.get("/trajets?faculte_id=&zone=arian")
    assert b"Ariana" in reponse.data and b"Sokra" not in reponse.data


def test_recherche_ecarte_trajets_passes_annules_et_complets(client):
    cond = creer_utilisateur("cond@isi.tn")
    creer_trajet(cond, zone="Passe", jours=-1)
    annule = creer_trajet(cond, zone="Annule")
    annule.statut = StatutTrajet.ANNULE
    complet = creer_trajet(cond, zone="Complet", places=1)
    complet.statut = StatutTrajet.COMPLET
    from app.extensions import db
    db.session.commit()
    creer_trajet(cond, zone="Visible")
    reponse = client.get("/trajets?faculte_id=")
    assert b"Visible" in reponse.data
    for zone in (b"Passe", b"Annule", b"Complet"):
        assert zone not in reponse.data


def test_recherche_sans_resultat_affiche_un_message(client):
    reponse = client.get("/trajets?faculte_id=&zone=introuvable")
    assert "Aucun trajet".encode() in reponse.data


def test_recherche_par_defaut_propose_la_faculte_de_l_utilisateur(client):
    cond = creer_utilisateur("cond@isi.tn")
    creer_utilisateur("fst@fst.tn", faculte_id=2)
    creer_trajet(cond, zone="VersISI", faculte_id=1)
    creer_trajet(cond, zone="VersFST", faculte_id=2)
    connecter(client, "fst@fst.tn")
    reponse = client.get("/trajets")
    assert b"VersFST" in reponse.data and b"VersISI" not in reponse.data


def test_modifier_son_trajet(client):
    cond = creer_utilisateur("cond@isi.tn")
    trajet = creer_trajet(cond)
    connecter(client, "cond@isi.tn")
    reponse = client.post(f"/trajets/{trajet.id}/modifier",
                          data=donnees_trajet(zone_depart="Ariana", places_total=4, prix="3"), follow_redirects=True)
    assert "Trajet modifié".encode() in reponse.data
    from app.extensions import db
    db.session.refresh(trajet)
    assert trajet.zone_depart == "Ariana" and trajet.places_total == 4 and trajet.prix == 3.0


def test_modifier_le_trajet_d_un_autre_est_interdit(client):
    cond = creer_utilisateur("cond@isi.tn")
    creer_utilisateur("autre@isi.tn")
    trajet = creer_trajet(cond)
    connecter(client, "autre@isi.tn")
    assert client.get(f"/trajets/{trajet.id}/modifier").status_code == 403
    assert client.post(f"/trajets/{trajet.id}/modifier", data=donnees_trajet()).status_code == 403
    assert client.post(f"/trajets/{trajet.id}/annuler").status_code == 403


def test_modifier_refuse_moins_de_places_que_de_reservations_confirmees(client):
    cond = creer_utilisateur("cond@isi.tn")
    p1, p2 = creer_utilisateur("p1@isi.tn"), creer_utilisateur("p2@isi.tn")
    trajet = creer_trajet(cond, places=2)
    for p in (p1, p2):
        accepter_reservation(demander_reservation(trajet, p))
    connecter(client, "cond@isi.tn")
    reponse = client.post(f"/trajets/{trajet.id}/modifier", data=donnees_trajet(places_total=1), follow_redirects=True)
    assert "déjà confirmées".encode() in reponse.data


def test_annuler_un_trajet_annule_ses_reservations(client):
    cond = creer_utilisateur("cond@isi.tn")
    pass1 = creer_utilisateur("p1@isi.tn")
    trajet = creer_trajet(cond)
    reservation = demander_reservation(trajet, pass1)
    connecter(client, "cond@isi.tn")
    reponse = client.post(f"/trajets/{trajet.id}/annuler", follow_redirects=True)
    assert "Trajet annulé".encode() in reponse.data
    from app.extensions import db
    db.session.refresh(trajet); db.session.refresh(reservation)
    assert trajet.statut == StatutTrajet.ANNULE and reservation.statut == StatutReservation.ANNULEE


def test_mes_trajets_liste_uniquement_mes_trajets(client):
    cond = creer_utilisateur("cond@isi.tn")
    autre = creer_utilisateur("autre@isi.tn")
    creer_trajet(cond, zone="MonTrajet")
    creer_trajet(autre, zone="TrajetAutre")
    connecter(client, "cond@isi.tn")
    reponse = client.get("/mes-trajets")
    assert b"MonTrajet" in reponse.data and b"TrajetAutre" not in reponse.data


def test_detail_d_un_trajet_inexistant(client):
    assert client.get("/trajets/9999").status_code == 404
