"""Règles métier des réservations et des trajets (couche « services » de l'architecture).

Les routes ne contiennent pas ces règles : elles appellent ces fonctions.
Cela correspond au contrôleur du diagramme de séquence de Jacobson, et rend
les règles faciles à tester séparément (BNF9).

Règles de gestion :
- RG01 : les réservations confirmées ne dépassent jamais le nombre de places ;
- RG02 : un passager ne réserve pas deux fois le même trajet ;
- RG03 : un conducteur ne réserve pas son propre trajet ;
- RG04 : on ne réserve que des trajets à venir.
"""
from ..extensions import db
from ..models import Reservation, StatutReservation, StatutTrajet, maintenant


class ReservationError(Exception):
    """Erreur de règle métier : son message est affiché à l'utilisateur."""


def demander_reservation(trajet, passager):
    """Le passager demande une place : la réservation est créée « En attente »."""
    if trajet.conducteur_id == passager.id:                       # RG03
        raise ReservationError("Vous ne pouvez pas réserver votre propre trajet.")
    if trajet.statut == StatutTrajet.ANNULE:
        raise ReservationError("Ce trajet a été annulé.")
    if trajet.est_passe():                                        # RG04
        raise ReservationError("Ce trajet est déjà passé.")
    if trajet.est_complet():                                      # RG01
        raise ReservationError("Plus de places disponibles sur ce trajet.")

    existante = Reservation.query.filter_by(trajet_id=trajet.id, passager_id=passager.id).first()
    if existante is not None:                                     # RG02
        if existante.statut == StatutReservation.ANNULEE:
            # Le passager avait annulé : il peut refaire une demande.
            existante.statut = StatutReservation.EN_ATTENTE
            existante.date_demande = maintenant()
            db.session.commit()
            return existante
        raise ReservationError(f"Vous avez déjà une demande pour ce trajet ({existante.statut.value}).")

    reservation = Reservation(trajet=trajet, passager=passager)
    db.session.add(reservation)
    db.session.commit()
    return reservation


def accepter_reservation(reservation):
    """Le conducteur accepte : la place est décomptée (la réservation devient « Confirmée »)."""
    if reservation.statut != StatutReservation.EN_ATTENTE:
        raise ReservationError("Cette demande a déjà été traitée.")
    trajet = reservation.trajet
    # On revérifie les places au moment de l'acceptation (scénario alternatif 11a).
    if trajet.est_complet():
        reservation.statut = StatutReservation.REFUSEE
        db.session.commit()
        raise ReservationError("Le trajet est complet : la demande a été refusée automatiquement.")
    reservation.statut = StatutReservation.CONFIRMEE
    if trajet.est_complet():
        trajet.statut = StatutTrajet.COMPLET
    db.session.commit()
    return reservation


def refuser_reservation(reservation):
    """Le conducteur refuse la demande."""
    if reservation.statut != StatutReservation.EN_ATTENTE:
        raise ReservationError("Cette demande a déjà été traitée.")
    reservation.statut = StatutReservation.REFUSEE
    db.session.commit()
    return reservation


def annuler_reservation(reservation):
    """Le passager annule sa réservation : la place est libérée si elle était confirmée."""
    if reservation.statut not in (StatutReservation.EN_ATTENTE, StatutReservation.CONFIRMEE):
        raise ReservationError("Cette réservation ne peut plus être annulée.")
    reservation.statut = StatutReservation.ANNULEE
    trajet = reservation.trajet
    if trajet.statut == StatutTrajet.COMPLET and not trajet.est_complet():
        trajet.statut = StatutTrajet.OUVERT
    db.session.commit()
    return reservation


def annuler_trajet(trajet):
    """Annule un trajet et toutes ses réservations en cours (BF5)."""
    if trajet.statut == StatutTrajet.ANNULE:
        raise ReservationError("Ce trajet est déjà annulé.")
    trajet.statut = StatutTrajet.ANNULE
    for reservation in trajet.reservations:
        if reservation.statut in (StatutReservation.EN_ATTENTE, StatutReservation.CONFIRMEE):
            reservation.statut = StatutReservation.ANNULEE
    db.session.commit()
    return trajet


def terminer_trajet(trajet):
    """Le conducteur marque un trajet comme terminé (possible une fois l'heure de départ passée)."""
    if trajet.statut == StatutTrajet.ANNULE:
        raise ReservationError("Un trajet annulé ne peut pas être terminé.")
    if trajet.statut == StatutTrajet.TERMINE:
        raise ReservationError("Ce trajet est déjà terminé.")
    if not trajet.est_passe():
        raise ReservationError("Le trajet ne peut être terminé qu'après son heure de départ.")
    trajet.statut = StatutTrajet.TERMINE
    db.session.commit()
    return trajet
