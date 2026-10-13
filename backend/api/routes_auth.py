"""connexion, déconnexion et compte de l'utilisateur connecté"""
from fastapi import APIRouter, HTTPException, Request, status

from backend.api.dependances import Jeton, SessionBD, UtilisateurConnecte
from backend.api.schemas import ChangementMotDePasse, DemandeConnexion, ReponseConnexion, UtilisateurPublic
from backend.auth.authentification import ConnexionRefusee, connecter, deconnecter
from backend.auth.securite import verifier_mot_de_passe
from backend.database.crud_utilisateurs import modifier_utilisateur

routeur = APIRouter(prefix="/auth", tags=["authentification"])


@routeur.post("/connexion", response_model=ReponseConnexion)
def connexion(demande : DemandeConnexion, request : Request, session : SessionBD) -> ReponseConnexion :
    adresse_ip = request.client.host if request.client else None
    try :
        utilisateur, jeton = connecter(session, demande.identifiant, demande.mot_de_passe, adresse_ip)
    except ConnexionRefusee as erreur :
        session.commit()        # la tentative refusée reste dans le journal
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(erreur)) from erreur
    session.commit()
    return ReponseConnexion(jeton=jeton, utilisateur=UtilisateurPublic.model_validate(utilisateur))


@routeur.post("/deconnexion", status_code=status.HTTP_204_NO_CONTENT)
def deconnexion(jeton : Jeton, session : SessionBD) -> None :
    deconnecter(session, jeton)
    session.commit()


@routeur.get("/moi", response_model=UtilisateurPublic)
def moi(utilisateur : UtilisateurConnecte) -> UtilisateurPublic :
    return UtilisateurPublic.model_validate(utilisateur)


@routeur.put("/moi/mot-de-passe", status_code=status.HTTP_204_NO_CONTENT)
def changer_mot_de_passe(changement : ChangementMotDePasse, utilisateur : UtilisateurConnecte, session : SessionBD) -> None :
    """change son propre mot de passe ; toutes les sessions du compte sont fermées (il faut se reconnecter)"""
    if not verifier_mot_de_passe(changement.ancien, utilisateur.mot_de_passe) :
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ancien mot de passe incorrect")
    modifier_utilisateur(session, utilisateur, mot_de_passe=changement.nouveau)
    session.commit()
