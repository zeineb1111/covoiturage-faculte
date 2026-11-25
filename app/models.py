"""Modèles de données : ils traduisent le diagramme de classes en tables.

Correspondance diagramme de classes -> base de données :
- chaque classe devient une table (Faculté, Utilisateur, Trajet, Réservation, Avis) ;
- chaque association « 1 vers plusieurs » devient une clé étrangère (ForeignKey) ;
- les énumérations (StatutTrajet, StatutReservation) sont des Enum Python ;
- Administrateur (sous-classe d'Utilisateur) est représenté par le champ `est_admin`.
"""
import enum
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def maintenant():
    """Date et heure actuelles (UTC)."""
    return datetime.now(timezone.utc)


class StatutTrajet(enum.Enum):
    OUVERT = "Ouvert"
    COMPLET = "Complet"
    ANNULE = "Annulé"
    TERMINE = "Terminé"


class StatutReservation(enum.Enum):
    EN_ATTENTE = "En attente"
    CONFIRMEE = "Confirmée"
    REFUSEE = "Refusée"
    ANNULEE = "Annulée"


class Faculte(db.Model):
    """Établissement universitaire : l'application peut être utilisée par n'importe quelle faculté.

    Un étudiant appartient à une faculté, et chaque trajet a pour destination une faculté.
    """
    __tablename__ = "faculte"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(120), unique=True, nullable=False)
    sigle = db.Column(db.String(20))
    ville = db.Column(db.String(60))

    utilisateurs = db.relationship("Utilisateur", back_populates="faculte")
    trajets = db.relationship("Trajet", back_populates="faculte")

    def __str__(self):
        return f"{self.sigle} - {self.nom}" if self.sigle else self.nom


class Utilisateur(UserMixin, db.Model):
    """Compte d'un étudiant (peut être conducteur et/ou passager) ou d'un administrateur."""
    __tablename__ = "utilisateur"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(60), nullable=False)
    prenom = db.Column(db.String(60), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    telephone = db.Column(db.String(20))
    # On ne stocke JAMAIS le mot de passe en clair, seulement son empreinte (hachage).
    mot_de_passe_hache = db.Column(db.String(255), nullable=False)
    statut_compte = db.Column(db.String(20), nullable=False, default="actif")
    est_admin = db.Column(db.Boolean, nullable=False, default=False)
    date_inscription = db.Column(db.DateTime, nullable=False, default=maintenant)
    # Faculté de l'étudiant (vide seulement pour un administrateur)
    faculte_id = db.Column(db.Integer, db.ForeignKey("faculte.id"))

    # Relations (côté « 1 » du diagramme de classes)
    faculte = db.relationship("Faculte", back_populates="utilisateurs")
    trajets = db.relationship("Trajet", back_populates="conducteur")
    reservations = db.relationship("Reservation", back_populates="passager")
    avis_ecrits = db.relationship("Avis", foreign_keys="Avis.auteur_id", back_populates="auteur")
    avis_recus = db.relationship("Avis", foreign_keys="Avis.destinataire_id", back_populates="destinataire")

    def definir_mot_de_passe(self, mot_de_passe):
        """Calcule et enregistre l'empreinte du mot de passe (BNF1)."""
        self.mot_de_passe_hache = generate_password_hash(mot_de_passe)

    def verifier_mot_de_passe(self, mot_de_passe):
        """Compare un mot de passe saisi avec l'empreinte enregistrée."""
        return check_password_hash(self.mot_de_passe_hache, mot_de_passe)

    def note_moyenne(self):
        """Moyenne des notes reçues (None s'il n'y a pas encore d'avis)."""
        notes = [a.note for a in self.avis_recus]
        return round(sum(notes) / len(notes), 1) if notes else None

    @property
    def est_actif(self):
        """Flask-Login refuse la connexion d'un compte suspendu."""
        return self.statut_compte == "actif"


@login_manager.user_loader
def charger_utilisateur(id_utilisateur):
    """Flask-Login appelle cette fonction pour retrouver l'utilisateur connecté."""
    return db.session.get(Utilisateur, int(id_utilisateur))


class Trajet(db.Model):
    """Offre de covoiturage publiée par un conducteur."""
    __tablename__ = "trajet"

    id = db.Column(db.Integer, primary_key=True)
    zone_depart = db.Column(db.String(80), nullable=False)
    # Destination du trajet : la faculté vers laquelle le conducteur se rend
    faculte_id = db.Column(db.Integer, db.ForeignKey("faculte.id"), nullable=False)
    date_depart = db.Column(db.Date, nullable=False)
    heure_depart = db.Column(db.Time, nullable=False)
    places_total = db.Column(db.Integer, nullable=False)
    prix = db.Column(db.Float, nullable=False, default=0.0)
    statut = db.Column(db.Enum(StatutTrajet), nullable=False, default=StatutTrajet.OUVERT)
    conducteur_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)

    conducteur = db.relationship("Utilisateur", back_populates="trajets")
    faculte = db.relationship("Faculte", back_populates="trajets")
    # Composition : si un trajet est supprimé, ses réservations le sont aussi.
    reservations = db.relationship("Reservation", back_populates="trajet", cascade="all, delete-orphan")
    avis = db.relationship("Avis", back_populates="trajet")

    def places_confirmees(self):
        """Nombre de places déjà prises (réservations confirmées)."""
        return sum(1 for r in self.reservations if r.statut == StatutReservation.CONFIRMEE)

    def places_restantes(self):
        return self.places_total - self.places_confirmees()

    def est_complet(self):
        return self.places_restantes() <= 0

    def est_passe(self):
        """Vrai si la date et l'heure de départ sont déjà passées (RG04)."""
        return datetime.combine(self.date_depart, self.heure_depart) < datetime.now()


class Reservation(db.Model):
    """Demande d'un passager pour une place sur un trajet."""
    __tablename__ = "reservation"
    # RG02 : un passager ne peut pas réserver deux fois le même trajet (BNF6).
    __table_args__ = (db.UniqueConstraint("trajet_id", "passager_id", name="uq_reservation_trajet_passager"),)

    id = db.Column(db.Integer, primary_key=True)
    date_demande = db.Column(db.DateTime, nullable=False, default=maintenant)
    statut = db.Column(db.Enum(StatutReservation), nullable=False, default=StatutReservation.EN_ATTENTE)
    trajet_id = db.Column(db.Integer, db.ForeignKey("trajet.id"), nullable=False)
    passager_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)

    trajet = db.relationship("Trajet", back_populates="reservations")
    passager = db.relationship("Utilisateur", back_populates="reservations")


class Avis(db.Model):
    """Note et commentaire laissés par un participant à un autre après un trajet."""
    __tablename__ = "avis"
    __table_args__ = (
        db.CheckConstraint("note BETWEEN 1 AND 5", name="ck_avis_note"),
        # Un auteur ne note qu'une fois une personne pour un trajet donné.
        db.UniqueConstraint("auteur_id", "destinataire_id", "trajet_id", name="uq_avis_auteur_dest_trajet"),
    )

    id = db.Column(db.Integer, primary_key=True)
    note = db.Column(db.Integer, nullable=False)
    commentaire = db.Column(db.String(500))
    date_avis = db.Column(db.DateTime, nullable=False, default=maintenant)
    auteur_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    destinataire_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"), nullable=False)
    trajet_id = db.Column(db.Integer, db.ForeignKey("trajet.id"), nullable=False)

    auteur = db.relationship("Utilisateur", foreign_keys=[auteur_id], back_populates="avis_ecrits")
    destinataire = db.relationship("Utilisateur", foreign_keys=[destinataire_id], back_populates="avis_recus")
    trajet = db.relationship("Trajet", back_populates="avis")
