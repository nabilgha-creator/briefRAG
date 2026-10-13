"""rôles d'accès a la documentation (quelles catégories de documents chaque rôle peut consulter) : réservé aux administrateurs"""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.dependances import Admin, SessionBD
from backend.api.schemas import CreationRole, ModificationRole, RolePublic
from backend.config import CATEGORIE_PAR_DEFAUT, CATEGORIES
from backend.database.crud_roles import categories_en_base, creer_role, get_role, lister_roles, modifier_role, supprimer_role
from backend.database.models import Role

routeur = APIRouter(prefix="/roles", tags=["rôles d'accès (admin)"])


def _role_ou_404(session : Session, id_role : int) -> Role :
    role = get_role(session, id_role)
    if role is None :
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rôle introuvable")
    return role


def _verifier_categories(categories : list[str] | None) -> None :
    inconnues = sorted(set(categories or []) - set(CATEGORIES))
    if inconnues :
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"catégorie(s) inconnue(s) : {', '.join(inconnues)}")


def _public(role : Role, nombre_comptes : int) -> RolePublic :
    return RolePublic(id_role=role.id_role, nom=role.nom, description=role.description, categories=role.categories,
                      nombre_comptes=nombre_comptes)


@routeur.get("/categories", response_model=list[str])
def categories(_ : Admin, session : SessionBD) -> list[str] :
    """catégories attribuables. "Document" (fichier rangé hors des dossiers connus) n'apparaît que s'il en existe"""
    en_base = categories_en_base(session)
    return [categorie for categorie in CATEGORIES if categorie != CATEGORIE_PAR_DEFAUT or categorie in en_base]


@routeur.get("", response_model=list[RolePublic])
def lister(_ : Admin, session : SessionBD) -> list[RolePublic] :
    return [_public(role, nombre) for role, nombre in lister_roles(session)]


@routeur.post("", response_model=RolePublic, status_code=status.HTTP_201_CREATED)
def creer(creation : CreationRole, _ : Admin, session : SessionBD) -> RolePublic :
    _verifier_categories(creation.categories)
    try :
        role = creer_role(session, creation.nom.strip(), creation.categories, creation.description)
    except ValueError as erreur :
        raise HTTPException(status.HTTP_409_CONFLICT, str(erreur)) from erreur
    session.commit()
    return _public(role, 0)


@routeur.patch("/{id_role}", response_model=RolePublic)
def modifier(id_role : int, modification : ModificationRole, _ : Admin, session : SessionBD) -> RolePublic :
    role = _role_ou_404(session, id_role)
    _verifier_categories(modification.categories)
    try :
        modifier_role(session, role, nom=modification.nom.strip() if modification.nom else None,
                      description=modification.description, categories=modification.categories)
    except ValueError as erreur :
        raise HTTPException(status.HTTP_409_CONFLICT, str(erreur)) from erreur
    session.commit()
    return _public(role, len(role.rel_utilisateur))


@routeur.delete("/{id_role}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer(id_role : int, _ : Admin, session : SessionBD) -> None :
    """les comptes qui avaient ce rôle le perdent"""
    supprimer_role(session, _role_ou_404(session, id_role))
    session.commit()
