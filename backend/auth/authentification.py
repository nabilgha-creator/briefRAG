"""connexion / déconnexion : vérifie les identifiants, journalise chaque tentative, gère les jetons de session.
ne connaît pas HTTP : l'API (backend/api) l'utilise."""
import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from sqlalchemy.orm import Session

from backend.auth.securite import hacher_mot_de_passe, verifier_mot_de_passe
from backend.database.crud_utilisateurs import (creer_jeton, get_utilisateur_par_identifiant, get_utilisateur_par_jeton,
                                               journaliser_connexion, supprimer_jeton, supprimer_jetons_expires)
from backend.database.models import Utilisateur

logger = logging.getLogger(__name__)

DUREE_SESSION = timedelta(hours=10)     # une journée de travail


class ConnexionRefusee(Exception) :
    """identifiant inconnu, mot de passe faux ou compte désactivé (même message dans tous les cas, volontairement)"""


@lru_cache
def _empreinte_factice() -> str :
    return hacher_mot_de_passe("mot-de-passe-factice")


def connecter(session : Session, identifiant : str, mot_de_passe : str, adresse_ip : str | None = None) -> tuple[Utilisateur, str] :
    """renvoie (utilisateur, jeton de session). chaque tentative est journalisée dans la table connexion"""
    utilisateur = get_utilisateur_par_identifiant(session, identifiant)
    # identifiant inconnu : on vérifie quand même une empreinte, pour que la durée de réponse ne trahisse rien
    mot_de_passe_ok = verifier_mot_de_passe(mot_de_passe, utilisateur.mot_de_passe if utilisateur else _empreinte_factice())
    valide = utilisateur is not None and utilisateur.actif and mot_de_passe_ok
    journaliser_connexion(session, identifiant, succes=valide, utilisateur=utilisateur, adresse_ip=adresse_ip)
    if not valide :
        logger.warning("connexion refusée pour %r depuis %s", identifiant, adresse_ip)
        raise ConnexionRefusee("identifiant ou mot de passe incorrect")

    supprimer_jetons_expires(session)
    utilisateur.derniere_connexion = datetime.now(timezone.utc)
    jeton = creer_jeton(session, utilisateur, DUREE_SESSION)
    logger.info("connexion de %s depuis %s", identifiant, adresse_ip)
    return utilisateur, jeton


def utilisateur_connecte(session : Session, jeton : str) -> Utilisateur | None :
    return get_utilisateur_par_jeton(session, jeton)


def deconnecter(session : Session, jeton : str) -> None :
    supprimer_jeton(session, jeton)
