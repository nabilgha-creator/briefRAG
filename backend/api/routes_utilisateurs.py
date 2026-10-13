"""gestion des utilisateurs et journal des connexions : réservé aux administrateurs"""
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.dependances import Admin, SessionBD
from backend.api.schemas import ConnexionJournal, CreationUtilisateur, ModificationUtilisateur, UtilisateurPublic
from backend.database.crud_utilisateurs import (compter_admins_actifs, creer_utilisateur, get_utilisateur, lister_connexions,
                                               lister_utilisateurs, modifier_utilisateur, supprimer_utilisateur)
from backend.database.models import Utilisateur

routeur = APIRouter(prefix="/utilisateurs", tags=["utilisateurs (admin)"])


def _utilisateur_ou_404(session : Session, id_utilisateur : int) -> Utilisateur :
    utilisateur = get_utilisateur(session, id_utilisateur)
    if utilisateur is None :
        raise HTTPException(status.HTTP_404_NOT_FOUND, "utilisateur introuvable")
    return utilisateur


def _verifier_reste_un_admin(session : Session, utilisateur : Utilisateur) -> None :
    """on ne retire jamais le dernier administrateur actif : plus personne ne pourrait gérer les comptes"""
    if utilisateur.role == "admin" and utilisateur.actif and compter_admins_actifs(session) <= 1 :
        raise HTTPException(status.HTTP_409_CONFLICT, "impossible : c'est le dernier administrateur actif")


@routeur.get("", response_model=list[UtilisateurPublic])
def lister(_ : Admin, session : SessionBD) -> list[Utilisateur] :
    return lister_utilisateurs(session)


@routeur.post("", response_model=UtilisateurPublic, status_code=status.HTTP_201_CREATED)
def creer(creation : CreationUtilisateur, _ : Admin, session : SessionBD) -> Utilisateur :
    try :
        utilisateur = creer_utilisateur(session, creation.identifiant, creation.nom, creation.mot_de_passe, creation.role)
    except ValueError as erreur :
        raise HTTPException(status.HTTP_409_CONFLICT, str(erreur)) from erreur
    session.commit()
    return utilisateur


@routeur.get("/connexions", response_model=list[ConnexionJournal])
def journal_connexions(_ : Admin, session : SessionBD, limite : int = Query(100, ge=1, le=1000),
                       id_utilisateur : int | None = None) -> list :
    return lister_connexions(session, limite, id_utilisateur)


@routeur.get("/{id_utilisateur}", response_model=UtilisateurPublic)
def detail(id_utilisateur : int, _ : Admin, session : SessionBD) -> Utilisateur :
    return _utilisateur_ou_404(session, id_utilisateur)


@routeur.patch("/{id_utilisateur}", response_model=UtilisateurPublic)
def modifier(id_utilisateur : int, modification : ModificationUtilisateur, _ : Admin, session : SessionBD) -> Utilisateur :
    utilisateur = _utilisateur_ou_404(session, id_utilisateur)
    if modification.actif is False or (modification.role is not None and modification.role != "admin") :
        _verifier_reste_un_admin(session, utilisateur)
    modifier_utilisateur(session, utilisateur, nom=modification.nom, mot_de_passe=modification.mot_de_passe,
                         role=modification.role, actif=modification.actif)
    session.commit()
    return utilisateur


@routeur.delete("/{id_utilisateur}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer(id_utilisateur : int, _ : Admin, session : SessionBD) -> None :
    utilisateur = _utilisateur_ou_404(session, id_utilisateur)
    _verifier_reste_un_admin(session, utilisateur)
    supprimer_utilisateur(session, utilisateur)
    session.commit()
