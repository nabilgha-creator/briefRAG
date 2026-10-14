"""formats des requêtes et réponses de l'API (validés par Pydantic, documentés automatiquement dans /docs)"""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from backend.auth.securite import LONGUEUR_MIN_MOT_DE_PASSE

Role = Literal["admin", "conseiller"]


class DepuisORM(BaseModel) :
    model_config = ConfigDict(from_attributes=True)


## AUTHENTIFICATION ##

class DemandeConnexion(BaseModel) :
    identifiant : str = Field(min_length=1, max_length=50)
    mot_de_passe : str = Field(min_length=1, max_length=200)


class RoleResume(DepuisORM) :
    id_role : int
    nom : str


class UtilisateurPublic(DepuisORM) :
    """un utilisateur, sans son empreinte de mot de passe.
    role : type de compte (droits de gestion) ; roles : rôles d'accès a la documentation"""
    id_utilisateur : int
    identifiant : str
    nom : str
    role : Role
    actif : bool
    date_creation : datetime
    derniere_connexion : datetime | None
    roles : list[RoleResume] = Field(default_factory=list, validation_alias=AliasChoices("rel_role", "roles"))


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
    roles : list[int] = []                  # identifiants des rôles d'accès a la documentation


class ModificationUtilisateur(BaseModel) :
    """seuls les champs envoyés sont modifiés (roles : remplace la liste des rôles d'accès)"""
    nom : str | None = Field(default=None, min_length=1, max_length=150)
    mot_de_passe : str | None = Field(default=None, min_length=LONGUEUR_MIN_MOT_DE_PASSE, max_length=200)
    role : Role | None = None
    actif : bool | None = None
    roles : list[int] | None = None


## RÔLES D'ACCÈS (admin) ##

class RolePublic(DepuisORM) :
    id_role : int
    nom : str
    description : str | None
    categories : list[str]
    nombre_comptes : int = 0


class CreationRole(BaseModel) :
    nom : str = Field(min_length=1, max_length=50)
    description : str | None = Field(default=None, max_length=255)
    categories : list[str] = []


class ModificationRole(BaseModel) :
    """seuls les champs envoyés sont modifiés"""
    nom : str | None = Field(default=None, min_length=1, max_length=50)
    description : str | None = Field(default=None, max_length=255)
    categories : list[str] | None = None


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
    extrait : str = ""
    distance : float | None = None      # None : donnée exacte (fiche erreur)
    document : str | None = None        # fichier a ouvrir dans le lecteur
    id_chunk : int | None = None        # passage a surligner (cf. GET /documents/passages/{id_chunk})


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


## LECTEUR DE DOCUMENTS ##

class Apercu(BaseModel) :
    """aperçu HTML d'un document docx, xlsx ou html (les pdf s'ouvrent avec GET /documents/fichier)"""
    source : str
    titre : str
    categorie : str
    html : str


class Passage(BaseModel) :
    """texte d'un chunk, sans sa ligne de contexte : le lecteur le retrouve dans le document pour le surligner"""
    id_chunk : int
    source : str
    pages : list[int]
    texte : str
