"""Règles métier des avis (BF12).

Un avis n'est possible qu'après le départ d'un trajet (non annulé), entre deux
participants : le passager note le conducteur, et le conducteur note chacun de
ses passagers confirmés. Un auteur ne note qu'une fois la même personne pour un trajet.
"""
from ..extensions import db
from ..models import Avis, StatutReservation, StatutTrajet


class AvisError(Exception):
    """Erreur de règle métier : son message est affiché à l'utilisateur."""


def participants_evaluables(trajet, utilisateur):
    """Liste des personnes que `utilisateur` peut encore noter pour ce trajet."""
    if trajet.statut == StatutTrajet.ANNULE:
        return []
    if not (trajet.statut == StatutTrajet.TERMINE or trajet.est_passe()):
        return []

    if utilisateur.id == trajet.conducteur_id:
        candidats = [r.passager for r in trajet.reservations if r.statut == StatutReservation.CONFIRMEE]
    elif any(r.passager_id == utilisateur.id and r.statut == StatutReservation.CONFIRMEE
             for r in trajet.reservations):
        candidats = [trajet.conducteur]
    else:
        return []

    deja_notes = {a.destinataire_id for a in trajet.avis if a.auteur_id == utilisateur.id}
    return [c for c in candidats if c.id not in deja_notes]


def creer_avis(trajet, auteur, destinataire, note, commentaire):
    """Enregistre un avis après vérification des règles."""
    if destinataire not in participants_evaluables(trajet, auteur):
        raise AvisError("Vous ne pouvez pas noter cette personne pour ce trajet.")
    if note is None or not 1 <= note <= 5:
        raise AvisError("La note doit être comprise entre 1 et 5.")
    commentaire = (commentaire or "").strip()
    if len(commentaire) > 500:
        raise AvisError("Le commentaire est limité à 500 caractères.")
    avis = Avis(note=note, commentaire=commentaire or None, auteur=auteur,
                destinataire=destinataire, trajet=trajet)
    db.session.add(avis)
    db.session.commit()
    return avis
