"""Routes d'authentification : inscription, connexion, déconnexion (BF1 et BF2)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import Faculte, Utilisateur

auth_bp = Blueprint("auth", __name__)

LONGUEUR_MIN_MOT_DE_PASSE = 8


@auth_bp.route("/inscription", methods=["GET", "POST"])
def inscription():
    """Affiche le formulaire d'inscription et crée le compte (BF1).

    L'étudiant choisit sa faculté dans la liste : l'application est ouverte
    à n'importe quelle faculté enregistrée.
    """
    if current_user.is_authenticated:
        return redirect(url_for("accueil"))

    facultes = Faculte.query.order_by(Faculte.nom).all()

    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        prenom = request.form.get("prenom", "").strip()
        email = request.form.get("email", "").strip().lower()
        telephone = request.form.get("telephone", "").strip()
        mot_de_passe = request.form.get("mot_de_passe", "")
        faculte = db.session.get(Faculte, request.form.get("faculte_id", type=int) or 0)

        # Validation côté serveur (BNF3) : on ne fait jamais confiance au navigateur.
        if not nom or not prenom or not email or not mot_de_passe:
            flash("Tous les champs obligatoires doivent être remplis.", "danger")
        elif faculte is None:
            flash("Veuillez choisir votre faculté dans la liste.", "danger")
        elif len(mot_de_passe) < LONGUEUR_MIN_MOT_DE_PASSE:
            flash(f"Le mot de passe doit contenir au moins {LONGUEUR_MIN_MOT_DE_PASSE} caractères.", "danger")
        elif Utilisateur.query.filter_by(email=email).first():
            flash("Un compte existe déjà avec cet e-mail.", "danger")
        else:
            utilisateur = Utilisateur(nom=nom, prenom=prenom, email=email, telephone=telephone,
                                      faculte=faculte)
            utilisateur.definir_mot_de_passe(mot_de_passe)
            db.session.add(utilisateur)
            db.session.commit()
            flash("Compte créé avec succès. Vous pouvez vous connecter.", "success")
            return redirect(url_for("auth.connexion"))

    return render_template("auth/inscription.html", facultes=facultes)


@auth_bp.route("/connexion", methods=["GET", "POST"])
def connexion():
    """Affiche le formulaire de connexion et ouvre la session (BF2)."""
    if current_user.is_authenticated:
        return redirect(url_for("accueil"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        mot_de_passe = request.form.get("mot_de_passe", "")
        utilisateur = Utilisateur.query.filter_by(email=email).first()

        # Même message dans tous les cas d'échec : on ne révèle pas si l'e-mail existe.
        if utilisateur is None or not utilisateur.verifier_mot_de_passe(mot_de_passe):
            flash("E-mail ou mot de passe incorrect.", "danger")
        elif not utilisateur.est_actif:
            flash("Ce compte est suspendu.", "danger")
        else:
            login_user(utilisateur)
            return redirect(url_for("accueil"))

    return render_template("auth/connexion.html")


@auth_bp.route("/deconnexion")
def deconnexion():
    """Ferme la session de l'utilisateur."""
    logout_user()
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("accueil"))


@auth_bp.route("/profil", methods=["GET", "POST"])
@login_required
def profil():
    """Consulter et modifier son profil, y compris le mot de passe (BF3)."""
    facultes = Faculte.query.order_by(Faculte.nom).all()
    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        prenom = request.form.get("prenom", "").strip()
        faculte = db.session.get(Faculte, request.form.get("faculte_id", type=int) or 0)
        ancien = request.form.get("ancien_mot_de_passe", "")
        nouveau = request.form.get("nouveau_mot_de_passe", "")

        if not nom or not prenom:
            flash("Le nom et le prénom sont obligatoires.", "danger")
        elif faculte is None and not current_user.est_admin:
            flash("Veuillez choisir votre faculté dans la liste.", "danger")
        elif nouveau and not current_user.verifier_mot_de_passe(ancien):
            flash("L'ancien mot de passe est incorrect.", "danger")
        elif nouveau and len(nouveau) < LONGUEUR_MIN_MOT_DE_PASSE:
            flash(f"Le nouveau mot de passe doit contenir au moins {LONGUEUR_MIN_MOT_DE_PASSE} caractères.", "danger")
        else:
            current_user.nom = nom
            current_user.prenom = prenom
            current_user.telephone = request.form.get("telephone", "").strip()
            if faculte is not None:
                current_user.faculte = faculte
            if nouveau:
                current_user.definir_mot_de_passe(nouveau)
            db.session.commit()
            flash("Profil mis à jour.", "success")
            return redirect(url_for("auth.profil"))
    return render_template("auth/profil.html", facultes=facultes)
