"""accès aux tables utilisateur, jeton et connexion. ne fait pas de commit : c'est l'appelant qui valide."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.database.models import Connexion, Jeton, Utilisateur
from backend.auth.securite import empreinte_jeton, generer_jeton, hacher_mot_de_passe

logger = logging.getLogger(__name__)


## UTILISATEURS ##

def get_utilisateur(session : Session, id_utilisateur : int) -> Utilisateur | None :
    return session.get(Utilisateur, id_utilisateur)


def get_utilisateur_par_identifiant(session : Session, identifiant : str) -> Utilisateur | None :
    return session.scalars(select(Utilisateur).where(Utilisateur.identifiant == identifiant)).one_or_none()


def lister_utilisateurs(session : Session) -> list[Utilisateur] :
    return list(session.scalars(select(Utilisateur).order_by(Utilisateur.identifiant)))


def creer_utilisateur(session : Session, identifiant : str, nom : str, mot_de_passe : str, role : str = "conseiller") -> Utilisateur :
    """lève ValueError si l'identifiant est déjà pris ou si le mot de passe est trop court"""
    if get_utilisateur_par_identifiant(session, identifiant) is not None :
        raise ValueError(f"l'identifiant {identifiant} est déjà utilisé")
    utilisateur = Utilisateur(identifiant=identifiant, nom=nom, mot_de_passe=hacher_mot_de_passe(mot_de_passe), role=role)
    session.add(utilisateur)
    session.flush()
    logger.info("utilisateur créé : %s (%s)", identifiant, role)
    return utilisateur


def modifier_utilisateur(session : Session, utilisateur : Utilisateur, nom : str | None = None, mot_de_passe : str | None = None,
                         role : str | None = None, actif : bool | None = None) -> Utilisateur :
    """modifie les champs donnés (None = inchangé). désactiver un compte ou changer son mot de passe ferme ses sessions"""
    if nom is not None :
        utilisateur.nom = nom
    if role is not None :
        utilisateur.role = role
    if actif is not None :
        utilisateur.actif = actif
    if mot_de_passe is not None :
        utilisateur.mot_de_passe = hacher_mot_de_passe(mot_de_passe)
    if mot_de_passe is not None or actif is False :
        supprimer_jetons(session, utilisateur)
    logger.info("utilisateur modifié : %s", utilisateur.identifiant)
    return utilisateur


def supprimer_utilisateur(session : Session, utilisateur : Utilisateur) -> None :
    """supprime le compte, ses sessions et ses conversations ; le journal des connexions est conservé"""
    logger.info("utilisateur supprimé : %s", utilisateur.identifiant)
    session.delete(utilisateur)


def compter_admins_actifs(session : Session) -> int :
    return len(session.scalars(select(Utilisateur.id_utilisateur).where(Utilisateur.role == "admin", Utilisateur.actif.is_(True))).all())


## JETONS DE SESSION ##

def creer_jeton(session : Session, utilisateur : Utilisateur, duree : timedelta) -> str :
    """crée une session et renvoie le jeton en clair (seule son empreinte est stockée)"""
    jeton = generer_jeton()
    session.add(Jeton(id_utilisateur=utilisateur.id_utilisateur, empreinte=empreinte_jeton(jeton),
                      expiration=datetime.now(timezone.utc) + duree))
    return jeton


def get_utilisateur_par_jeton(session : Session, jeton : str) -> Utilisateur | None :
    """l'utilisateur de la session, si le jeton existe, n'a pas expiré et que le compte est actif"""
    stmt = (select(Utilisateur).join(Jeton)
            .where(Jeton.empreinte == empreinte_jeton(jeton), Jeton.expiration > datetime.now(timezone.utc), Utilisateur.actif.is_(True)))
    return session.scalars(stmt).one_or_none()


def supprimer_jeton(session : Session, jeton : str) -> None :
    session.execute(delete(Jeton).where(Jeton.empreinte == empreinte_jeton(jeton)))


def supprimer_jetons(session : Session, utilisateur : Utilisateur) -> None :
    session.execute(delete(Jeton).where(Jeton.id_utilisateur == utilisateur.id_utilisateur))


def supprimer_jetons_expires(session : Session) -> int :
    return session.execute(delete(Jeton).where(Jeton.expiration <= datetime.now(timezone.utc))).rowcount


## JOURNAL DES CONNEXIONS ##

def journaliser_connexion(session : Session, identifiant : str, succes : bool, utilisateur : Utilisateur | None = None,
                          adresse_ip : str | None = None) -> None :
    session.add(Connexion(identifiant=identifiant[:50], succes=succes, adresse_ip=adresse_ip,
                          id_utilisateur=utilisateur.id_utilisateur if utilisateur else None))


def lister_connexions(session : Session, limite : int = 100, id_utilisateur : int | None = None) -> list[Connexion] :
    stmt = select(Connexion).order_by(Connexion.date.desc(), Connexion.id_connexion.desc()).limit(limite)
    if id_utilisateur is not None :
        stmt = stmt.where(Connexion.id_utilisateur == id_utilisateur)
    return list(session.scalars(stmt))
