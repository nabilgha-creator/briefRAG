"""accès aux tables conversation et message. ne fait pas de commit : c'est l'appelant qui valide."""
import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database.models import Conversation, Message

logger = logging.getLogger(__name__)

LONGUEUR_TITRE = 80
TITRE_PAR_DEFAUT = "Nouvelle conversation"      # remplacé par le début de la 1re question


def titre_depuis_question(question : str) -> str :
    """titre de conversation tiré de la 1re question (sans appel au LLM : aucun coût)"""
    titre = " ".join(question.split())
    return titre if len(titre) <= LONGUEUR_TITRE else titre[:LONGUEUR_TITRE - 1].rsplit(" ", 1)[0] + "…"


def creer_conversation(session : Session, id_utilisateur : int, titre : str = TITRE_PAR_DEFAUT) -> Conversation :
    conversation = Conversation(id_utilisateur=id_utilisateur, titre=titre[:150])
    session.add(conversation)
    session.flush()
    return conversation


def get_conversation(session : Session, id_conversation : int, id_utilisateur : int) -> Conversation | None :
    """la conversation, seulement si elle appartient a cet utilisateur"""
    stmt = select(Conversation).where(Conversation.id_conversation == id_conversation, Conversation.id_utilisateur == id_utilisateur)
    return session.scalars(stmt).one_or_none()


def lister_conversations(session : Session, id_utilisateur : int) -> list[Conversation] :
    """les conversations de l'utilisateur, la plus récemment active d'abord"""
    stmt = select(Conversation).where(Conversation.id_utilisateur == id_utilisateur).order_by(Conversation.date_maj.desc())
    return list(session.scalars(stmt))


def renommer_conversation(session : Session, conversation : Conversation, titre : str) -> Conversation :
    conversation.titre = titre[:150]
    return conversation


def supprimer_conversation(session : Session, conversation : Conversation) -> None :
    session.delete(conversation)


def ajouter_message(session : Session, conversation : Conversation, role : str, contenu : str, sources : list[dict] | None = None,
                    modele_llm : str | None = None, tokens_entree : int | None = None, tokens_sortie : int | None = None,
                    cout : float | None = None, contact_sav : bool = False) -> Message :
    message = Message(role=role, contenu=contenu, sources=sources, modele_llm=modele_llm, tokens_entree=tokens_entree,
                      tokens_sortie=tokens_sortie, cout=Decimal(str(cout)) if cout is not None else None, contact_sav=contact_sav)
    conversation.rel_message.append(message)
    conversation.date_maj = func.now()      # la conversation remonte en tête de liste
    session.add(message)
    session.flush()
    return message


def derniers_messages(session : Session, conversation : Conversation, nombre : int) -> list[Message] :
    """les `nombre` derniers messages, du plus ancien au plus récent"""
    stmt = (select(Message).where(Message.id_conversation == conversation.id_conversation)
            .order_by(Message.id_message.desc()).limit(nombre))
    return list(session.scalars(stmt))[::-1]
