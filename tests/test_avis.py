"""Tests des avis (BF12) et de la clôture d'un trajet."""
import pytest

from app.extensions import db
from app.models import Avis, StatutTrajet
from app.services.avis import AvisError, creer_avis, participants_evaluables
from app.services.reservations import accepter_reservation, demander_reservation
from tests.helpers import connecter, creer_trajet, creer_utilisateur


@pytest.fixture
def trajet_passe(app):
    """Un trajet déjà effectué : un conducteur, un passager confirmé et un passager refusé."""
    cond = creer_utilisateur("cond@isi.tn", prenom="Cond")
    pass_ok = creer_utilisateur("ok@isi.tn", prenom="Confirme")
    pass_att = creer_utilisateur("att@isi.tn", prenom="Attente")
    trajet = creer_trajet(cond, places=3, jours=-1)
    # Les réservations sont créées directement (demander_reservation refuse un trajet passé).
    from app.models import Reservation, StatutReservation
    db.session.add_all([Reservation(trajet=trajet, passager=pass_ok, statut=StatutReservation.CONFIRMEE),
                        Reservation(trajet=trajet, passager=pass_att, statut=StatutReservation.EN_ATTENTE)])
    db.session.commit()
    return cond, pass_ok, pass_att, trajet


def test_le_passager_peut_noter_le_conducteur(trajet_passe):
    cond, pass_ok, _, trajet = trajet_passe
    assert participants_evaluables(trajet, pass_ok) == [cond]
    avis = creer_avis(trajet, pass_ok, cond, 5, "Très ponctuel")
    assert avis.note == 5 and cond.note_moyenne() == 5.0


def test_le_conducteur_note_ses_passagers_confirmes_seulement(trajet_passe):
    cond, pass_ok, pass_att, trajet = trajet_passe
    assert participants_evaluables(trajet, cond) == [pass_ok]
    with pytest.raises(AvisError):
        creer_avis(trajet, cond, pass_att, 4, "")


def test_un_avis_par_personne_et_par_trajet(trajet_passe):
    cond, pass_ok, _, trajet = trajet_passe
    creer_avis(trajet, pass_ok, cond, 4, "")
    assert participants_evaluables(trajet, pass_ok) == []
    with pytest.raises(AvisError):
        creer_avis(trajet, pass_ok, cond, 5, "")
    assert Avis.query.count() == 1


def test_pas_d_avis_avant_le_depart(app):
    cond, passager = creer_utilisateur("cond@isi.tn"), creer_utilisateur("p@isi.tn")
    trajet = creer_trajet(cond, jours=2)
    accepter_reservation(demander_reservation(trajet, passager))
    assert participants_evaluables(trajet, passager) == []
    with pytest.raises(AvisError):
        creer_avis(trajet, passager, cond, 5, "")


def test_pas_d_avis_sur_un_trajet_annule(trajet_passe):
    cond, pass_ok, _, trajet = trajet_passe
    trajet.statut = StatutTrajet.ANNULE
    db.session.commit()
    assert participants_evaluables(trajet, pass_ok) == []


def test_un_etranger_au_trajet_ne_peut_pas_noter(trajet_passe):
    cond, _, _, trajet = trajet_passe
    etranger = creer_utilisateur("etranger@isi.tn")
    with pytest.raises(AvisError):
        creer_avis(trajet, etranger, cond, 5, "")


def test_note_et_commentaire_valides(trajet_passe):
    cond, pass_ok, _, trajet = trajet_passe
    for note in (0, 6, None):
        with pytest.raises(AvisError, match="entre 1 et 5"):
            creer_avis(trajet, pass_ok, cond, note, "")
    with pytest.raises(AvisError, match="500"):
        creer_avis(trajet, pass_ok, cond, 3, "x" * 501)


def test_note_moyenne_de_plusieurs_avis(trajet_passe):
    cond, pass_ok, _, trajet = trajet_passe
    autre = creer_utilisateur("autre@isi.tn")
    trajet2 = creer_trajet(cond, jours=-2)
    from app.models import Reservation, StatutReservation
    db.session.add(Reservation(trajet=trajet2, passager=autre, statut=StatutReservation.CONFIRMEE))
    db.session.commit()
    creer_avis(trajet, pass_ok, cond, 5, "")
    creer_avis(trajet2, autre, cond, 4, "")
    assert cond.note_moyenne() == 4.5


def test_parcours_terminer_puis_noter_depuis_les_pages(client, trajet_passe):
    cond, pass_ok, _, trajet = trajet_passe
    connecter(client, "cond@isi.tn")
    reponse = client.get(f"/trajets/{trajet.id}")
    assert "Marquer comme terminé".encode() in reponse.data
    reponse = client.post(f"/trajets/{trajet.id}/terminer", follow_redirects=True)
    assert "Trajet terminé".encode() in reponse.data
    assert "Laisser un avis".encode() in reponse.data          # le conducteur peut noter son passager
    client.get("/deconnexion")

    connecter(client, "ok@isi.tn")
    reponse = client.post(f"/trajets/{trajet.id}/avis",
                          data={"destinataire_id": cond.id, "note": 5, "commentaire": "Parfait"},
                          follow_redirects=True)
    assert "votre avis a été publié".encode() in reponse.data and b"Parfait" in reponse.data


def test_terminer_refuse_a_un_autre_que_le_conducteur(client, trajet_passe):
    _, _, _, trajet = trajet_passe
    creer_utilisateur("autre@isi.tn")
    connecter(client, "autre@isi.tn")
    assert client.post(f"/trajets/{trajet.id}/terminer").status_code == 403


def test_noter_exige_une_connexion(client, trajet_passe):
    trajet = trajet_passe[3]
    reponse = client.post(f"/trajets/{trajet.id}/avis", data={"destinataire_id": 1, "note": 5})
    assert reponse.status_code == 302 and "/connexion" in reponse.headers["Location"]
