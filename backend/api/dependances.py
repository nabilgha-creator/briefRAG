"""dépendances des routes : session (annulée si erreur, toujours fermée), utilisateur connecté, droits admin.
les routes qui écrivent font session.commit() elles-mêmes"""
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.auth.authentification import utilisateur_connecte
from backend.database.db import SessionLocal
from backend.database.models import Utilisateur

_schema_bearer = HTTPBearer(auto_error=False)       # en-tête "Authorization: Bearer <jeton>"


def get_session() -> Iterator[Session] :
    with SessionLocal() as session :
        try :
            yield session
        except Exception :
            session.rollback()
            raise


SessionBD = Annotated[Session, Depends(get_session)]


def get_jeton(identifiants : Annotated[HTTPAuthorizationCredentials | None, Depends(_schema_bearer)]) -> str :
    if identifiants is None :
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "connexion requise", headers={"WWW-Authenticate": "Bearer"})
    return identifiants.credentials


Jeton = Annotated[str, Depends(get_jeton)]


def get_utilisateur(session : SessionBD, jeton : Jeton) -> Utilisateur :
    utilisateur = utilisateur_connecte(session, jeton)
    if utilisateur is None :
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expirée ou invalide", headers={"WWW-Authenticate": "Bearer"})
    return utilisateur


UtilisateurConnecte = Annotated[Utilisateur, Depends(get_utilisateur)]


def get_admin(utilisateur : UtilisateurConnecte) -> Utilisateur :
    if utilisateur.role != "admin" :
        raise HTTPException(status.HTTP_403_FORBIDDEN, "réservé aux administrateurs")
    return utilisateur


Admin = Annotated[Utilisateur, Depends(get_admin)]
