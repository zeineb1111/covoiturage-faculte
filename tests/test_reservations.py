"""Tests des réservations et de leurs règles de gestion RG01 à RG04 (BF6 à BF11)."""
import pytest

from app.extensions import db
from app.models import Reservation, StatutReservation, StatutTrajet
from app.services.reservations import (ReservationError, accepter_reservation, annuler_reservation,
                                       demander_reservation, refuser_reservation, terminer_trajet)
from tests.helpers import connecter, creer_trajet, creer_utilisateur


@pytest.fixture
def scene(app):
    """Un conducteur, deux passagers et un trajet de 2 places."""
    cond = creer_utilisateur("cond@isi.tn", prenom="Cond")
    p1 = creer_utilisateur("p1@isi.tn", prenom="Premier")
    p2 = creer_utilisateur("p2@isi.tn", prenom="Second")
    trajet = creer_trajet(cond, places=2)
    return cond, p1, p2, trajet


# ---------- règles métier (couche services) ----------

def test_une_demande_est_creee_en_attente(scene):
    _, p1, _, trajet = scene
    reservation = demander_reservation(trajet, p1)
    assert reservation.statut == StatutReservation.EN_ATTENTE
    assert trajet.places_restantes() == 2          # la place n'est décomptée qu'à l'acceptation


def test_rg03_le_conducteur_ne_reserve_pas_son_trajet(scene):
    cond, _, _, trajet = scene
    with pytest.raises(ReservationError, match="propre trajet"):
        demander_reservation(trajet, cond)


def test_rg02_pas_de_double_reservation(scene):
    _, p1, _, trajet = scene
    demander_reservation(trajet, p1)
    with pytest.raises(ReservationError, match="déjà une demande"):
        demander_reservation(trajet, p1)
    assert Reservation.query.count() == 1


def test_rg04_pas_de_reservation_sur_un_trajet_passe(scene):
    cond, p1, _, _ = scene
    passe = creer_trajet(cond, jours=-1)
    with pytest.raises(ReservationError, match="déjà passé"):
        demander_reservation(passe, p1)


def test_pas_de_reservation_sur_un_trajet_annule(scene):
    _, p1, _, trajet = scene
    trajet.statut = StatutTrajet.ANNULE
    db.session.commit()
    with pytest.raises(ReservationError, match="annulé"):
        demander_reservation(trajet, p1)


def test_accepter_decompte_une_place(scene):
    _, p1, _, trajet = scene
    reservation = accepter_reservation(demander_reservation(trajet, p1))
    assert reservation.statut == StatutReservation.CONFIRMEE
    assert trajet.places_restantes() == 1 and trajet.statut == StatutTrajet.OUVERT


def test_rg01_trajet_complet_quand_toutes_les_places_sont_prises(scene):
    _, p1, p2, trajet = scene
    accepter_reservation(demander_reservation(trajet, p1))
    accepter_reservation(demander_reservation(trajet, p2))
    assert trajet.places_restantes() == 0 and trajet.statut == StatutTrajet.COMPLET
    nouveau = creer_utilisateur("p3@isi.tn")
    with pytest.raises(ReservationError, match="Plus de places"):
        demander_reservation(trajet, nouveau)


def test_rg01_acceptation_refusee_si_le_trajet_est_devenu_complet(scene):
    """Scénario alternatif 11a : deux demandes en attente pour une seule place."""
    cond, p1, p2, _ = scene
    trajet = creer_trajet(cond, places=1)
    r1, r2 = demander_reservation(trajet, p1), demander_reservation(trajet, p2)
    accepter_reservation(r1)
    with pytest.raises(ReservationError, match="complet"):
        accepter_reservation(r2)
    assert r2.statut == StatutReservation.REFUSEE
    assert trajet.places_confirmees() == 1


def test_refuser_une_demande(scene):
    _, p1, _, trajet = scene
    reservation = refuser_reservation(demander_reservation(trajet, p1))
    assert reservation.statut == StatutReservation.REFUSEE and trajet.places_restantes() == 2


def test_une_demande_deja_traitee_ne_peut_pas_etre_retraitee(scene):
    _, p1, _, trajet = scene
    reservation = accepter_reservation(demander_reservation(trajet, p1))
    with pytest.raises(ReservationError):
        accepter_reservation(reservation)
    with pytest.raises(ReservationError):
        refuser_reservation(reservation)


def test_annuler_libere_la_place_et_rouvre_le_trajet(scene):
    _, p1, p2, trajet = scene
    r1 = accepter_reservation(demander_reservation(trajet, p1))
    accepter_reservation(demander_reservation(trajet, p2))
    assert trajet.statut == StatutTrajet.COMPLET
    annuler_reservation(r1)
    assert r1.statut == StatutReservation.ANNULEE
    assert trajet.places_restantes() == 1 and trajet.statut == StatutTrajet.OUVERT


def test_un_passager_peut_refaire_une_demande_apres_annulation(scene):
    _, p1, _, trajet = scene
    reservation = demander_reservation(trajet, p1)
    annuler_reservation(reservation)
    nouvelle = demander_reservation(trajet, p1)
    assert nouvelle.id == reservation.id and nouvelle.statut == StatutReservation.EN_ATTENTE
    assert Reservation.query.count() == 1


def test_terminer_un_trajet_seulement_apres_le_depart(scene):
    cond, _, _, trajet = scene
    with pytest.raises(ReservationError, match="après son heure"):
        terminer_trajet(trajet)
    passe = creer_trajet(cond, jours=-1)
    assert terminer_trajet(passe).statut == StatutTrajet.TERMINE


# ---------- pages et boutons ----------

def test_parcours_complet_reserver_accepter(client, scene):
    """Le passager demande, le conducteur accepte, le passager voit « Confirmée »."""
    cond, p1, _, trajet = scene
    connecter(client, "p1@isi.tn")
    reponse = client.post(f"/trajets/{trajet.id}/reserver", follow_redirects=True)
    assert "Demande envoyée".encode() in reponse.data and "En attente".encode() in reponse.data
    client.get("/deconnexion")

    connecter(client, "cond@isi.tn")
    reponse = client.get(f"/trajets/{trajet.id}")
    assert b"Accepter" in reponse.data and b"Refuser" in reponse.data
    reservation = Reservation.query.one()
    reponse = client.post(f"/reservations/{reservation.id}/accepter", follow_redirects=True)
    assert "Réservation confirmée".encode() in reponse.data
    client.get("/deconnexion")

    connecter(client, "p1@isi.tn")
    reponse = client.get("/mes-reservations")
    assert "Confirmée".encode() in reponse.data


def test_reserver_exige_une_connexion(client, scene):
    trajet = scene[3]
    reponse = client.post(f"/trajets/{trajet.id}/reserver")
    assert reponse.status_code == 302 and "/connexion" in reponse.headers["Location"]


def test_le_conducteur_ne_voit_pas_le_bouton_reserver(client, scene):
    trajet = scene[3]
    connecter(client, "cond@isi.tn")
    reponse = client.get(f"/trajets/{trajet.id}")
    assert "Réserver une place".encode() not in reponse.data


def test_seul_le_conducteur_peut_accepter_ou_refuser(client, scene):
    _, p1, p2, trajet = scene
    reservation = demander_reservation(trajet, p1)
    connecter(client, "p2@isi.tn")
    assert client.post(f"/reservations/{reservation.id}/accepter").status_code == 403
    assert client.post(f"/reservations/{reservation.id}/refuser").status_code == 403
    db.session.refresh(reservation)
    assert reservation.statut == StatutReservation.EN_ATTENTE


def test_seul_le_passager_peut_annuler_sa_reservation(client, scene):
    _, p1, p2, trajet = scene
    reservation = demander_reservation(trajet, p1)
    connecter(client, "p2@isi.tn")
    assert client.post(f"/reservations/{reservation.id}/annuler").status_code == 403
    client.get("/deconnexion")
    connecter(client, "p1@isi.tn")
    reponse = client.post(f"/reservations/{reservation.id}/annuler", follow_redirects=True)
    assert "Réservation annulée".encode() in reponse.data


def test_double_reservation_refusee_depuis_la_page(client, scene):
    trajet = scene[3]
    connecter(client, "p1@isi.tn")
    client.post(f"/trajets/{trajet.id}/reserver")
    reponse = client.post(f"/trajets/{trajet.id}/reserver", follow_redirects=True)
    assert "déjà une demande".encode() in reponse.data
    assert Reservation.query.count() == 1


def test_mes_reservations_ne_montre_que_les_miennes(client, scene):
    cond, p1, p2, _ = scene
    t1, t2 = creer_trajet(cond, zone="ZoneUn"), creer_trajet(cond, zone="ZoneDeux")
    demander_reservation(t1, p1)
    demander_reservation(t2, p2)
    connecter(client, "p1@isi.tn")
    reponse = client.get("/mes-reservations")
    assert b"ZoneUn" in reponse.data and b"ZoneDeux" not in reponse.data
