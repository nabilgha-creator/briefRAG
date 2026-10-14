"""conversations et questions : réponse en JSON (POST .../messages) ou en SSE (POST .../messages/flux),
événements morceau (texte) puis fin (sources, consommation) ou erreur"""
import json
import logging
from collections.abc import Iterator
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.api.dependances import SessionBD, UtilisateurConnecte
from backend.api.schemas import (ConversationDetail, ConversationResume, CreationConversation, MessagePublic, Question,
                                 RenommageConversation, ReponseQuestion)
from backend.auth.droits import categories_autorisees
from backend.database.crud_conversations import (TITRE_PAR_DEFAUT, creer_conversation, get_conversation, lister_conversations,
                                                 renommer_conversation, supprimer_conversation)
from backend.database.db import SessionLocal
from backend.database.models import Conversation
from backend.rag.assistant import Preparation, ReponseAssistant, enregistrer_echange, historique_conversation, preparer, repondre
from backend.rag.llm import ErreurLLM, FluxLLM

logger = logging.getLogger(__name__)

routeur = APIRouter(prefix="/conversations", tags=["conversations"])


def _conversation_ou_404(session : Session, id_conversation : int, id_utilisateur : int) -> Conversation :
    conversation = get_conversation(session, id_conversation, id_utilisateur)
    if conversation is None :
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation introuvable")
    return conversation


def _reponse_question(reponse : ReponseAssistant) -> ReponseQuestion :
    return ReponseQuestion(id_message=reponse.message.id_message, reponse=reponse.texte,
                           sources=[asdict(source) for source in reponse.sources],
                           consommation=asdict(reponse.consommation) if reponse.consommation else None,
                           contact_sav=reponse.contact_sav)


@routeur.get("", response_model=list[ConversationResume])
def lister(utilisateur : UtilisateurConnecte, session : SessionBD) -> list[Conversation] :
    return lister_conversations(session, utilisateur.id_utilisateur)


@routeur.post("", response_model=ConversationResume, status_code=status.HTTP_201_CREATED)
def creer(creation : CreationConversation, utilisateur : UtilisateurConnecte, session : SessionBD) -> Conversation :
    conversation = creer_conversation(session, utilisateur.id_utilisateur, creation.titre or TITRE_PAR_DEFAUT)
    session.commit()
    return conversation


@routeur.get("/{id_conversation}", response_model=ConversationDetail)
def detail(id_conversation : int, utilisateur : UtilisateurConnecte, session : SessionBD) -> ConversationDetail :
    conversation = _conversation_ou_404(session, id_conversation, utilisateur.id_utilisateur)
    return ConversationDetail(id_conversation=conversation.id_conversation, titre=conversation.titre,
                              date_creation=conversation.date_creation, date_maj=conversation.date_maj,
                              messages=[MessagePublic.model_validate(message) for message in conversation.rel_message])


@routeur.patch("/{id_conversation}", response_model=ConversationResume)
def renommer(id_conversation : int, renommage : RenommageConversation, utilisateur : UtilisateurConnecte, session : SessionBD) -> Conversation :
    conversation = _conversation_ou_404(session, id_conversation, utilisateur.id_utilisateur)
    renommer_conversation(session, conversation, renommage.titre)
    session.commit()
    return conversation


@routeur.delete("/{id_conversation}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer(id_conversation : int, utilisateur : UtilisateurConnecte, session : SessionBD) -> None :
    supprimer_conversation(session, _conversation_ou_404(session, id_conversation, utilisateur.id_utilisateur))
    session.commit()


@routeur.post("/{id_conversation}/messages", response_model=ReponseQuestion)
def poser_question(id_conversation : int, question : Question, utilisateur : UtilisateurConnecte, session : SessionBD) -> ReponseQuestion :
    conversation = _conversation_ou_404(session, id_conversation, utilisateur.id_utilisateur)
    try :
        reponse = repondre(session, conversation, question.question, categories_autorisees(utilisateur))
    except ErreurLLM as erreur :
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(erreur)) from erreur
    session.commit()
    return _reponse_question(reponse)


def _evenement(nom : str, donnees : dict) -> str :
    return f"event: {nom}\ndata: {json.dumps(donnees, ensure_ascii=False, default=str)}\n\n"


def _flux_reponse(id_conversation : int, preparation : Preparation) -> Iterator[str] :
    """envoie la réponse morceau par morceau puis l'enregistre. tourne après la fin de la route :
    il ouvre donc sa propre session pour l'enregistrement"""
    if preparation.messages is None :
        texte, consommation = preparation.reponse_directe, None
        yield _evenement("morceau", {"texte": texte})
    else :
        flux, morceaux = FluxLLM(preparation.messages), []
        try :
            for morceau in flux :
                morceaux.append(morceau)
                yield _evenement("morceau", {"texte": morceau})
        except ErreurLLM as erreur :
            logger.error("conversation %d : %s", id_conversation, erreur)
            yield _evenement("erreur", {"message": str(erreur)})
            return
        texte, consommation = "".join(morceaux), flux.consommation

    with SessionLocal() as session :
        conversation = session.get(Conversation, id_conversation)
        reponse = enregistrer_echange(session, conversation, preparation, texte, consommation)
        session.commit()
        yield _evenement("fin", _reponse_question(reponse).model_dump(exclude={"reponse"}))


@routeur.post("/{id_conversation}/messages/flux")
def poser_question_flux(id_conversation : int, question : Question, utilisateur : UtilisateurConnecte, session : SessionBD) -> StreamingResponse :
    conversation = _conversation_ou_404(session, id_conversation, utilisateur.id_utilisateur)
    preparation = preparer(session, question.question, historique_conversation(session, conversation), categories_autorisees(utilisateur))
    return StreamingResponse(_flux_reponse(conversation.id_conversation, preparation), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
