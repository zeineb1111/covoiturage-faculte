"""Routes des réservations : demander, accepter, refuser, annuler, historique (BF6 à BF11).

Ces routes vérifient QUI a le droit d'agir, puis appellent les règles métier
du module services.reservations.
"""
from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Reservation, Trajet
from ..services import reservations as service
from ..services.reservations import ReservationError

reservations_bp = Blueprint("reservations", __name__)


@reservations_bp.route("/trajets/<int:trajet_id>/reserver", methods=["POST"])
@login_required
def reserver(trajet_id):
    """Le passager demande une place sur un trajet (BF9)."""
    trajet = db.get_or_404(Trajet, trajet_id)
    try:
        service.demander_reservation(trajet, current_user)
        flash("Demande envoyée au conducteur. Elle est en attente de sa réponse.", "success")
    except ReservationError as erreur:
        flash(str(erreur), "danger")
    return redirect(url_for("trajets.detail", trajet_id=trajet.id))


def _reservation_du_conducteur(reservation_id):
    """Retourne la réservation si l'utilisateur connecté est le conducteur du trajet."""
    reservation = db.get_or_404(Reservation, reservation_id)
    if reservation.trajet.conducteur_id != current_user.id:
        abort(403)
    return reservation


@reservations_bp.route("/reservations/<int:reservation_id>/accepter", methods=["POST"])
@login_required
def accepter(reservation_id):
    """Le conducteur accepte une demande (BF7)."""
    reservation = _reservation_du_conducteur(reservation_id)
    try:
        service.accepter_reservation(reservation)
        flash("Réservation confirmée.", "success")
    except ReservationError as erreur:
        flash(str(erreur), "warning")
    return redirect(url_for("trajets.detail", trajet_id=reservation.trajet_id))


@reservations_bp.route("/reservations/<int:reservation_id>/refuser", methods=["POST"])
@login_required
def refuser(reservation_id):
    """Le conducteur refuse une demande (BF7)."""
    reservation = _reservation_du_conducteur(reservation_id)
    try:
        service.refuser_reservation(reservation)
        flash("Demande refusée.", "info")
    except ReservationError as erreur:
        flash(str(erreur), "warning")
    return redirect(url_for("trajets.detail", trajet_id=reservation.trajet_id))


@reservations_bp.route("/reservations/<int:reservation_id>/annuler", methods=["POST"])
@login_required
def annuler(reservation_id):
    """Le passager annule sa réservation (BF10)."""
    reservation = db.get_or_404(Reservation, reservation_id)
    if reservation.passager_id != current_user.id:
        abort(403)
    try:
        service.annuler_reservation(reservation)
        flash("Réservation annulée.", "info")
    except ReservationError as erreur:
        flash(str(erreur), "warning")
    return redirect(url_for("reservations.mes_reservations"))


@reservations_bp.route("/mes-reservations")
@login_required
def mes_reservations():
    """Historique des réservations du passager connecté (BF11)."""
    reservations = (Reservation.query.filter_by(passager_id=current_user.id)
                    .order_by(Reservation.date_demande.desc()).all())
    return render_template("reservations/mes_reservations.html", reservations=reservations)
