"""Extensions Flask partagées par toute l'application.

Elles sont créées ici (sans application) pour éviter les imports circulaires,
puis rattachées à l'application dans create_app().
"""
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
# Protection CSRF : chaque formulaire POST doit contenir un jeton secret (sécurité, BNF2/BNF3).
csrf = CSRFProtect()
# Page vers laquelle on redirige un visiteur non connecté qui demande une page protégée.
login_manager.login_view = "auth.connexion"
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
login_manager.login_message_category = "warning"
