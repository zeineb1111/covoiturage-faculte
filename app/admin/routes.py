"""Espace administrateur : comptes, facultés, trajets (BF13, BF14, BF15)."""
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Avis, Faculte, Reservation, StatutTrajet, Trajet, Utilisateur
from ..services.reservations import ReservationError, annuler_trajet

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_requis(vue):
    """Réserve une page aux administrateurs (BNF2) : les autres reçoivent une erreur 403."""
    @wraps(vue)
    @login_required
    def vue_protegee(*args, **kwargs):
        if not current_user.est_admin:
            abort(403)
        return vue(*args, **kwargs)
    return vue_protegee


@admin_bp.route("/")
@admin_requis
def tableau_de_bord():
    """Chiffres clés de la plateforme."""
    stats = {
        "utilisateurs": Utilisateur.query.count(),
        "facultes": Faculte.query.count(),
        "trajets_ouverts": Trajet.query.filter_by(statut=StatutTrajet.OUVERT).count(),
        "reservations": Reservation.query.count(),
        "avis": Avis.query.count(),
    }
    return render_template("admin/tableau.html", stats=stats)


@admin_bp.route("/utilisateurs")
@admin_requis
def utilisateurs():
    """Liste des comptes (BF13)."""
    return render_template("admin/utilisateurs.html",
                           utilisateurs=Utilisateur.query.order_by(Utilisateur.nom).all())


@admin_bp.route("/utilisateurs/<int:utilisateur_id>/statut", methods=["POST"])
@admin_requis
def changer_statut(utilisateur_id):
    """Suspend ou réactive un compte (BF13)."""
    utilisateur = db.get_or_404(Utilisateur, utilisateur_id)
    if utilisateur.id == current_user.id or utilisateur.est_admin:
        flash("Un administrateur ne peut pas être suspendu.", "warning")
    elif utilisateur.statut_compte == "actif":
        utilisateur.statut_compte = "suspendu"
        db.session.commit()
        flash(f"Compte de {utilisateur.prenom} {utilisateur.nom} suspendu.", "info")
    else:
        utilisateur.statut_compte = "actif"
        db.session.commit()
        flash(f"Compte de {utilisateur.prenom} {utilisateur.nom} réactivé.", "success")
    return redirect(url_for("admin.utilisateurs"))


@admin_bp.route("/facultes", methods=["GET", "POST"])
@admin_requis
def facultes():
    """Liste des facultés et ajout d'une nouvelle faculté (BF15)."""
    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        sigle = request.form.get("sigle", "").strip()
        ville = request.form.get("ville", "").strip()
        if not nom:
            flash("Le nom de la faculté est obligatoire.", "danger")
        elif Faculte.query.filter(db.func.lower(Faculte.nom) == nom.lower()).first():
            flash("Cette faculté existe déjà.", "danger")
        else:
            db.session.add(Faculte(nom=nom, sigle=sigle or None, ville=ville or None))
            db.session.commit()
            flash(f"Faculté « {nom} » ajoutée : ses étudiants peuvent maintenant s'inscrire.", "success")
        return redirect(url_for("admin.facultes"))
    return render_template("admin/facultes.html", facultes=Faculte.query.order_by(Faculte.nom).all())


@admin_bp.route("/facultes/<int:faculte_id>/modifier", methods=["POST"])
@admin_requis
def modifier_faculte(faculte_id):
    """Modifie le nom, le sigle ou la ville d'une faculté (BF15)."""
    faculte = db.get_or_404(Faculte, faculte_id)
    nom = request.form.get("nom", "").strip()
    doublon = Faculte.query.filter(db.func.lower(Faculte.nom) == nom.lower(), Faculte.id != faculte.id).first()
    if not nom:
        flash("Le nom de la faculté est obligatoire.", "danger")
    elif doublon:
        flash("Une autre faculté porte déjà ce nom.", "danger")
    else:
        faculte.nom = nom
        faculte.sigle = request.form.get("sigle", "").strip() or None
        faculte.ville = request.form.get("ville", "").strip() or None
        db.session.commit()
        flash("Faculté modifiée.", "success")
    return redirect(url_for("admin.facultes"))


@admin_bp.route("/trajets")
@admin_requis
def trajets():
    """Liste de tous les trajets, pour modération (BF14)."""
    return render_template("admin/trajets.html",
                           trajets=Trajet.query.order_by(Trajet.date_depart.desc()).all())


@admin_bp.route("/trajets/<int:trajet_id>/retirer", methods=["POST"])
@admin_requis
def retirer_trajet(trajet_id):
    """Retire un trajet abusif : il est annulé et disparaît de la recherche (BF14)."""
    trajet = db.get_or_404(Trajet, trajet_id)
    try:
        annuler_trajet(trajet)
        flash("Trajet retiré de la plateforme.", "info")
    except ReservationError as erreur:
        flash(str(erreur), "warning")
    return redirect(url_for("admin.trajets"))


@admin_bp.route("/avis")
@admin_requis
def avis():
    """Liste des avis, pour modération (BF14)."""
    return render_template("admin/avis.html", avis=Avis.query.order_by(Avis.date_avis.desc()).all())


@admin_bp.route("/avis/<int:avis_id>/supprimer", methods=["POST"])
@admin_requis
def supprimer_avis(avis_id):
    """Supprime un avis abusif (BF14)."""
    db.session.delete(db.get_or_404(Avis, avis_id))
    db.session.commit()
    flash("Avis supprimé.", "info")
    return redirect(url_for("admin.avis"))
