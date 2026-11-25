"""Route des avis : noter un conducteur ou un passager après un trajet (BF12)."""
from flask import Blueprint, flash, redirect, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Trajet, Utilisateur
from ..services.avis import AvisError, creer_avis

avis_bp = Blueprint("avis", __name__)


@avis_bp.route("/trajets/<int:trajet_id>/avis", methods=["POST"])
@login_required
def noter(trajet_id):
    trajet = db.get_or_404(Trajet, trajet_id)
    destinataire = db.session.get(Utilisateur, request.form.get("destinataire_id", type=int) or 0)
    try:
        if destinataire is None:
            raise AvisError("Personne à noter introuvable.")
        creer_avis(trajet, current_user, destinataire,
                   request.form.get("note", type=int), request.form.get("commentaire"))
        flash("Merci, votre avis a été publié.", "success")
    except AvisError as erreur:
        flash(str(erreur), "danger")
    return redirect(url_for("trajets.detail", trajet_id=trajet.id))
