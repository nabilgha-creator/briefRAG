"""assistant RAG : question + historique -> recherche du contexte -> prompt -> LLM -> réponse et sources citées.

deux étapes séparées pour permettre le streaming :
1. preparer() : recherche et construction du prompt (ou réponse directe sans LLM quand il faut demander le modèle)
2. enregistrer_echange() : une fois la réponse obtenue, question et réponse sont enregistrées ensemble
   (si le LLM échoue, rien n'est enregistré : pas de question orpheline dans l'historique)
ne connaît ni HTTP ni l'interface : utilisé par l'API (backend/api) et par le mode terminal (backend/rag/terminal.py).
"""
import logging
import re
from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from backend.database.crud_conversations import TITRE_PAR_DEFAUT, ajouter_message, derniers_messages, titre_depuis_question
from backend.database.models import Conversation, Message
from backend.rag.llm import Consommation, completer
from backend.rag.prompts import MESSAGE_PRECISION_MODELE, construire_messages
from backend.rag.recherche import Reference, rechercher_contexte

logger = logging.getLogger(__name__)

MAX_MESSAGES_HISTORIQUE = 6         # 3 derniers échanges renvoyés au LLM
MAX_CARACTERES_MESSAGE = 1500       # une longue réponse passée est tronquée dans l'historique envoyé au LLM
RE_CITATION = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")      # [2], [2][3], [2, 3]


@dataclass
class Preparation :
    question : str
    messages : list[dict[str, str]] | None      # None : réponse directe, sans appel au LLM
    reponse_directe : str | None
    references : list[Reference]


@dataclass
class ReponseAssistant :
    texte : str
    sources : list[Reference]
    message : Message | None = None
    consommation : Consommation | None = None


def historique_conversation(session : Session, conversation : Conversation) -> list[dict[str, str]] :
    """derniers messages au format du LLM, les plus longs tronqués"""
    return [{"role": message.role, "content": message.contenu[:MAX_CARACTERES_MESSAGE]}
            for message in derniers_messages(session, conversation, MAX_MESSAGES_HISTORIQUE)]


def preparer(session : Session, question : str, historique : list[dict[str, str]]) -> Preparation :
    questions_precedentes = [message["content"] for message in historique if message["role"] == "user"]
    contexte = rechercher_contexte(session, question, questions_precedentes)
    if contexte.besoin_precision :
        logger.info("code erreur sans appareil : demande du modèle, sans appel au LLM")
        return Preparation(question=question, messages=None, reponse_directe=MESSAGE_PRECISION_MODELE, references=[])
    messages = construire_messages(question, historique[-MAX_MESSAGES_HISTORIQUE:], contexte)
    return Preparation(question=question, messages=messages, reponse_directe=None, references=contexte.references())


def references_citees(texte : str, references : list[Reference]) -> list[Reference] :
    """les sources effectivement citées dans la réponse ([1], [2][3]...), dans l'ordre de leur numéro"""
    numeros = {int(numero) for groupe in RE_CITATION.findall(texte) for numero in re.split(r"[,;]", groupe)}
    return [reference for reference in references if reference.numero in numeros]


def enregistrer_echange(session : Session, conversation : Conversation, preparation : Preparation, texte : str,
                        consommation : Consommation | None = None) -> ReponseAssistant :
    """enregistre la question et la réponse (avec ses sources citées et sa consommation) ; titre la conversation a sa 1re question"""
    if conversation.titre == TITRE_PAR_DEFAUT :
        conversation.titre = titre_depuis_question(preparation.question)
    sources = references_citees(texte, preparation.references)
    ajouter_message(session, conversation, "user", preparation.question)
    message = ajouter_message(session, conversation, "assistant", texte, sources=[asdict(source) for source in sources],
                              modele_llm=consommation.modele if consommation else None,
                              tokens_entree=consommation.tokens_entree if consommation else None,
                              tokens_sortie=consommation.tokens_sortie if consommation else None,
                              cout=consommation.cout if consommation else None)
    return ReponseAssistant(texte=texte, sources=sources, message=message, consommation=consommation)


def repondre(session : Session, conversation : Conversation, question : str) -> ReponseAssistant :
    """réponse complète (sans streaming), enregistrée dans la conversation"""
    preparation = preparer(session, question, historique_conversation(session, conversation))
    if preparation.messages is None :
        return enregistrer_echange(session, conversation, preparation, preparation.reponse_directe)
    reponse = completer(preparation.messages)
    return enregistrer_echange(session, conversation, preparation, reponse.texte, reponse.consommation)
