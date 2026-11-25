"""Routes des trajets : publier, rechercher, consulter, modifier, annuler (BF4, BF5, BF8)."""
from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Faculte, Reservation, StatutReservation, StatutTrajet, Trajet
from ..services.avis import participants_evaluables
from ..services.reservations import ReservationError, annuler_trajet, terminer_trajet

trajets_bp = Blueprint("trajets", __name__)

PLACES_MAX = 8


def lire_formulaire_trajet():
    """Lit et valide le formulaire d'un trajet.

    Retourne (erreurs, donnees). Toute la validation se fait côté serveur (BNF3).
    """
    erreurs = []
    faculte = db.session.get(Faculte, request.form.get("faculte_id", type=int) or 0)
    zone = request.form.get("zone_depart", "").strip()
    donnees = {"faculte": faculte, "zone_depart": zone, "date_depart": None,
               "heure_depart": None, "places_total": None, "prix": None}

    if faculte is None:
        erreurs.append("Veuillez choisir la faculté de destination.")
    if not zone or len(zone) > 80:
        erreurs.append("La zone de départ est obligatoire (80 caractères maximum).")

    try:
        donnees["date_depart"] = datetime.strptime(request.form.get("date_depart", ""), "%Y-%m-%d").date()
        donnees["heure_depart"] = datetime.strptime(request.form.get("heure_depart", ""), "%H:%M").time()
        # RG04 : le départ doit être dans le futur
        if datetime.combine(donnees["date_depart"], donnees["heure_depart"]) < datetime.now():
            erreurs.append("La date et l'heure de départ doivent être dans le futur.")
    except ValueError:
        erreurs.append("Date ou heure de départ invalide.")

    places = request.form.get("places_total", type=int)
    if places is None or not 1 <= places <= PLACES_MAX:
        erreurs.append(f"Le nombre de places doit être compris entre 1 et {PLACES_MAX}.")
    else:
        donnees["places_total"] = places

    try:
        prix = float(request.form.get("prix", "").replace(",", "."))
        if prix < 0:
            raise ValueError
        donnees["prix"] = prix
    except ValueError:
        erreurs.append("Le prix doit être un nombre positif ou nul.")

    return erreurs, donnees


@trajets_bp.route("/trajets")
def recherche():
    """Recherche de trajets par faculté de destination, zone de départ et date (BF8)."""
    facultes = Faculte.query.order_by(Faculte.nom).all()

    # Par défaut, on propose la faculté de l'utilisateur connecté.
    if "faculte_id" in request.args:
        faculte_id = request.args.get("faculte_id", type=int)
    else:
        faculte_id = current_user.faculte_id if current_user.is_authenticated else None
    zone = request.args.get("zone", "").strip()
    date_texte = request.args.get("date", "")

    requete = Trajet.query.filter(Trajet.statut == StatutTrajet.OUVERT, Trajet.date_depart >= date.today())
    if faculte_id:
        requete = requete.filter(Trajet.faculte_id == faculte_id)
    if zone:
        requete = requete.filter(Trajet.zone_depart.ilike(f"%{zone}%"))
    if date_texte:
        try:
            requete = requete.filter(Trajet.date_depart == datetime.strptime(date_texte, "%Y-%m-%d").date())
        except ValueError:
            flash("Date de recherche invalide.", "warning")

    # Les trajets déjà passés aujourd'hui sont écartés.
    trajets = [t for t in requete.order_by(Trajet.date_depart, Trajet.heure_depart).all() if not t.est_passe()]
    return render_template("trajets/recherche.html", trajets=trajets, facultes=facultes,
                           faculte_id=faculte_id, zone=zone, date_texte=date_texte)


@trajets_bp.route("/trajets/nouveau", methods=["GET", "POST"])
@login_required
def nouveau():
    """Publie un trajet (BF4). Le conducteur est l'utilisateur connecté."""
    facultes = Faculte.query.order_by(Faculte.nom).all()
    if request.method == "POST":
        erreurs, d = lire_formulaire_trajet()
        if erreurs:
            for e in erreurs:
                flash(e, "danger")
        else:
            trajet = Trajet(conducteur=current_user, faculte=d["faculte"], zone_depart=d["zone_depart"],
                            date_depart=d["date_depart"], heure_depart=d["heure_depart"],
                            places_total=d["places_total"], prix=d["prix"])
            db.session.add(trajet)
            db.session.commit()
            flash("Trajet publié avec succès.", "success")
            return redirect(url_for("trajets.detail", trajet_id=trajet.id))
    return render_template("trajets/formulaire.html", facultes=facultes, trajet=None,
                           aujourdhui=date.today().isoformat())


@trajets_bp.route("/trajets/<int:trajet_id>")
def detail(trajet_id):
    """Détail d'un trajet. Le conducteur y voit aussi les demandes de réservation (BF6)."""
    trajet = db.get_or_404(Trajet, trajet_id)
    est_conducteur = current_user.is_authenticated and trajet.conducteur_id == current_user.id
    reservation = None
    if current_user.is_authenticated and not est_conducteur:
        reservation = Reservation.query.filter_by(trajet_id=trajet.id, passager_id=current_user.id).first()
    evaluables = participants_evaluables(trajet, current_user) if current_user.is_authenticated else []
    return render_template("trajets/detail.html", trajet=trajet, est_conducteur=est_conducteur,
                           reservation=reservation, evaluables=evaluables,
                           StatutReservation=StatutReservation, StatutTrajet=StatutTrajet)


@trajets_bp.route("/trajets/<int:trajet_id>/modifier", methods=["GET", "POST"])
@login_required
def modifier(trajet_id):
    """Modifie un trajet publié (BF5). Réservé à son conducteur."""
    trajet = db.get_or_404(Trajet, trajet_id)
    if trajet.conducteur_id != current_user.id:
        abort(403)
    if trajet.statut == StatutTrajet.ANNULE:
        flash("Un trajet annulé ne peut pas être modifié.", "warning")
        return redirect(url_for("trajets.detail", trajet_id=trajet.id))

    facultes = Faculte.query.order_by(Faculte.nom).all()
    if request.method == "POST":
        erreurs, d = lire_formulaire_trajet()
        # On ne peut pas descendre sous le nombre de places déjà confirmées (RG01).
        if d["places_total"] is not None and d["places_total"] < trajet.places_confirmees():
            erreurs.append(f"{trajet.places_confirmees()} place(s) sont déjà confirmées : "
                           "le nombre de places ne peut pas être inférieur.")
        if erreurs:
            for e in erreurs:
                flash(e, "danger")
        else:
            trajet.faculte = d["faculte"]
            trajet.zone_depart = d["zone_depart"]
            trajet.date_depart = d["date_depart"]
            trajet.heure_depart = d["heure_depart"]
            trajet.places_total = d["places_total"]
            trajet.prix = d["prix"]
            trajet.statut = StatutTrajet.COMPLET if trajet.est_complet() else StatutTrajet.OUVERT
            db.session.commit()
            flash("Trajet modifié.", "success")
            return redirect(url_for("trajets.detail", trajet_id=trajet.id))
    return render_template("trajets/formulaire.html", facultes=facultes, trajet=trajet,
                           aujourdhui=date.today().isoformat())


@trajets_bp.route("/trajets/<int:trajet_id>/annuler", methods=["POST"])
@login_required
def annuler(trajet_id):
    """Annule un trajet et ses réservations (BF5). Réservé à son conducteur."""
    trajet = db.get_or_404(Trajet, trajet_id)
    if trajet.conducteur_id != current_user.id:
        abort(403)
    try:
        annuler_trajet(trajet)
        flash("Trajet annulé. Les passagers concernés verront leur réservation annulée.", "info")
    except ReservationError as erreur:
        flash(str(erreur), "warning")
    return redirect(url_for("trajets.mes_trajets"))


@trajets_bp.route("/trajets/<int:trajet_id>/terminer", methods=["POST"])
@login_required
def terminer(trajet_id):
    """Marque un trajet comme terminé, ce qui ouvre la possibilité de laisser des avis."""
    trajet = db.get_or_404(Trajet, trajet_id)
    if trajet.conducteur_id != current_user.id:
        abort(403)
    try:
        terminer_trajet(trajet)
        flash("Trajet terminé. Vous pouvez maintenant noter vos passagers.", "success")
    except ReservationError as erreur:
        flash(str(erreur), "warning")
    return redirect(url_for("trajets.detail", trajet_id=trajet.id))


@trajets_bp.route("/mes-trajets")
@login_required
def mes_trajets():
    """Liste des trajets publiés par l'utilisateur connecté."""
    trajets = (Trajet.query.filter_by(conducteur_id=current_user.id)
               .order_by(Trajet.date_depart.desc(), Trajet.heure_depart.desc()).all())
    return render_template("trajets/mes_trajets.html", trajets=trajets)
