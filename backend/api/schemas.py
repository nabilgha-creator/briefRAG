"""formats des requêtes et réponses de l'API (validés par Pydantic, documentés automatiquement dans /docs)"""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.auth.securite import LONGUEUR_MIN_MOT_DE_PASSE

Role = Literal["admin", "conseiller"]


class DepuisORM(BaseModel) :
    model_config = ConfigDict(from_attributes=True)


## AUTHENTIFICATION ##

class DemandeConnexion(BaseModel) :
    identifiant : str = Field(min_length=1, max_length=50)
    mot_de_passe : str = Field(min_length=1, max_length=200)


class UtilisateurPublic(DepuisORM) :
    """un utilisateur, sans son empreinte de mot de passe"""
    id_utilisateur : int
    identifiant : str
    nom : str
    role : Role
    actif : bool
    date_creation : datetime
    derniere_connexion : datetime | None


class ReponseConnexion(BaseModel) :
    jeton : str
    utilisateur : UtilisateurPublic


class ChangementMotDePasse(BaseModel) :
    ancien : str = Field(min_length=1, max_length=200)
    nouveau : str = Field(min_length=LONGUEUR_MIN_MOT_DE_PASSE, max_length=200)


## UTILISATEURS (admin) ##

class CreationUtilisateur(BaseModel) :
    identifiant : str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9._-]+$")
    nom : str = Field(min_length=1, max_length=150)
    mot_de_passe : str = Field(min_length=LONGUEUR_MIN_MOT_DE_PASSE, max_length=200)
    role : Role = "conseiller"


class ModificationUtilisateur(BaseModel) :
    """seuls les champs envoyés sont modifiés"""
    nom : str | None = Field(default=None, min_length=1, max_length=150)
    mot_de_passe : str | None = Field(default=None, min_length=LONGUEUR_MIN_MOT_DE_PASSE, max_length=200)
    role : Role | None = None
    actif : bool | None = None


class ConnexionJournal(DepuisORM) :
    id_connexion : int
    id_utilisateur : int | None
    identifiant : str
    date : datetime
    succes : bool
    adresse_ip : str | None


## CONVERSATIONS ##

class Source(BaseModel) :
    numero : int
    titre : str
    source : str
    pages : list[int] = []


class MessagePublic(DepuisORM) :
    id_message : int
    role : Literal["user", "assistant"]
    contenu : str
    sources : list[Source] | None
    date : datetime


class ConversationResume(DepuisORM) :
    id_conversation : int
    titre : str
    date_creation : datetime
    date_maj : datetime


class ConversationDetail(ConversationResume) :
    messages : list[MessagePublic]


class CreationConversation(BaseModel) :
    titre : str | None = Field(default=None, min_length=1, max_length=150)


class RenommageConversation(BaseModel) :
    titre : str = Field(min_length=1, max_length=150)


class Question(BaseModel) :
    question : str = Field(min_length=1, max_length=2000)      # plafond : protège le coût en tokens


class Consommation(BaseModel) :
    modele : str
    tokens_entree : int | None
    tokens_sortie : int | None
    cout : Decimal | float | None


class ReponseQuestion(BaseModel) :
    id_message : int
    reponse : str
    sources : list[Source]
    consommation : Consommation | None
