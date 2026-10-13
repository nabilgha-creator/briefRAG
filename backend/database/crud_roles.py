"""accès aux rôles d'accès a la documentation. ne fait pas de commit : c'est l'appelant qui valide."""
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database.models import Document, Role, utilisateur_role

logger = logging.getLogger(__name__)


def lister_roles(session : Session) -> list[tuple[Role, int]] :
    """les rôles triés par nom, avec leur nombre de comptes"""
    nombre = (select(func.count()).select_from(utilisateur_role).where(utilisateur_role.c.id_role == Role.id_role)
              .correlate(Role).scalar_subquery())
    return list(session.execute(select(Role, nombre).order_by(Role.nom)).tuples())


def get_role(session : Session, id_role : int) -> Role | None :
    return session.get(Role, id_role)


def get_roles(session : Session, ids_roles : list[int]) -> list[Role] :
    """les rôles demandés ; lève ValueError si l'un n'existe pas"""
    roles = list(session.scalars(select(Role).where(Role.id_role.in_(ids_roles))))
    inconnus = set(ids_roles) - {role.id_role for role in roles}
    if inconnus :
        raise ValueError(f"rôle(s) inconnu(s) : {sorted(inconnus)}")
    return roles


def get_role_par_nom(session : Session, nom : str) -> Role | None :
    return session.scalars(select(Role).where(func.lower(Role.nom) == nom.lower())).one_or_none()


def creer_role(session : Session, nom : str, categories : list[str], description : str | None = None) -> Role :
    """lève ValueError si le nom est déjà pris"""
    if get_role_par_nom(session, nom) is not None :
        raise ValueError(f"le rôle {nom} existe déjà")
    role = Role(nom=nom, description=description, categories=sorted(set(categories)))
    session.add(role)
    session.flush()
    logger.info("rôle créé : %s (%s)", nom, ", ".join(role.categories) or "aucune catégorie")
    return role


def modifier_role(session : Session, role : Role, nom : str | None = None, description : str | None = None,
                  categories : list[str] | None = None) -> Role :
    """modifie les champs donnés (None = inchangé) ; lève ValueError si le nouveau nom est déjà pris"""
    if nom is not None and nom.lower() != role.nom.lower() :
        if get_role_par_nom(session, nom) is not None :
            raise ValueError(f"le rôle {nom} existe déjà")
        role.nom = nom
    elif nom is not None :
        role.nom = nom                  # même nom, casse différente
    if description is not None :
        role.description = description or None
    if categories is not None :
        role.categories = sorted(set(categories))
    logger.info("rôle modifié : %s", role.nom)
    return role


def supprimer_role(session : Session, role : Role) -> None :
    """supprime le rôle ; les comptes qui l'avaient le perdent (liaisons supprimées en cascade)"""
    logger.info("rôle supprimé : %s", role.nom)
    session.delete(role)


def categories_en_base(session : Session) -> list[str] :
    """catégories des documents actuellement en base"""
    return list(session.scalars(select(Document.categorie).distinct().order_by(Document.categorie)))
