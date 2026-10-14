"""compte admin d'amorçage du .env (ADMIN_IDENTIFIANT, ADMIN_EMPREINTE : python -m backend.auth.empreinte).
créé ou rétabli au démarrage seulement si aucun administrateur actif n'existe"""
import logging
import os

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from backend.auth.securite import empreinte_valide
from backend.database.crud_utilisateurs import (compter_admins_actifs, creer_utilisateur_avec_empreinte,
                                               get_utilisateur_par_identifiant, supprimer_jetons)

load_dotenv()

logger = logging.getLogger(__name__)


def assurer_admin_initial(session : Session) -> None :
    """crée ou rétablit le compte d'amorçage si aucun administrateur actif n'existe (l'appelant valide la transaction)"""
    if compter_admins_actifs(session) > 0 :
        return

    identifiant = os.getenv("ADMIN_IDENTIFIANT", "").strip()
    empreinte = os.getenv("ADMIN_EMPREINTE", "").strip()
    nom = os.getenv("ADMIN_NOM", "").strip() or "Administrateur"
    if not identifiant or not empreinte :
        logger.warning("aucun administrateur actif et pas de compte d'amorçage : renseignez ADMIN_IDENTIFIANT et "
                       "ADMIN_EMPREINTE dans le .env (empreinte : python -m backend.auth.empreinte), puis redémarrez l'API")
        return
    if not empreinte_valide(empreinte) :
        logger.error("ADMIN_EMPREINTE n'est pas une empreinte valide : générez-la avec python -m backend.auth.empreinte")
        return

    existant = get_utilisateur_par_identifiant(session, identifiant)
    if existant is None :
        creer_utilisateur_avec_empreinte(session, identifiant, nom, empreinte, role="admin")
        logger.warning("compte administrateur d'amorçage %r créé depuis le .env", identifiant)
    else :
        existant.role, existant.actif, existant.mot_de_passe = "admin", True, empreinte
        supprimer_jetons(session, existant)
        logger.warning("aucun administrateur actif : compte %r rétabli en administrateur depuis le .env", identifiant)
