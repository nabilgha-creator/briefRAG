"""assistant RAG en deux temps (pour le streaming) : preparer() (recherche + prompt, ou réponse sans LLM),
puis enregistrer_echange() (question et réponse ensemble : rien si le LLM échoue)"""
import logging
import re
from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from backend.database.crud_conversations import TITRE_PAR_DEFAUT, ajouter_message, derniers_messages, titre_depuis_question
from backend.database.models import Conversation, Message
from backend.rag.llm import Consommation, completer
from backend.rag.prompts import MARQUEUR_SAV, MESSAGE_PRECISION_MODELE, construire_messages
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
    contact_sav : bool = False


def separer_contact_sav(texte : str) -> tuple[str, bool] :
    """(réponse sans le marqueur [SAV], marqueur présent ?)"""
    return texte.replace(MARQUEUR_SAV, "").rstrip(), MARQUEUR_SAV in texte


def pour_historique(texte : str, titres_sources : list[str] | None = None) -> str :
    """message renvoyé au LLM dans l'historique : tronqué, sans les [n] (le LLM les prendrait pour les sources du tour
    en cours), suivi des titres des sources citées : sans eux, il croit avoir inventé ce qu'il ne retrouve plus"""
    texte = re.sub(r"\s*" + RE_CITATION.pattern, "", texte)[:MAX_CARACTERES_MESSAGE]
    return f"{texte}\n(Sources de cette réponse : {' ; '.join(titres_sources)})" if titres_sources else texte


def historique_conversation(session : Session, conversation : Conversation) -> list[dict[str, str]] :
    """derniers messages au format du LLM"""
    return [{"role": message.role, "content": pour_historique(message.contenu, [source["titre"] for source in message.sources or []])}
            for message in derniers_messages(session, conversation, MAX_MESSAGES_HISTORIQUE)]


def preparer(session : Session, question : str, historique : list[dict[str, str]], categories : list[str] | None = None) -> Preparation :
    """categories : catégories de documents que l'utilisateur peut consulter (None = toutes, cf. auth/droits.py)"""
    questions_precedentes = [message["content"] for message in historique if message["role"] == "user"]
    contexte = rechercher_contexte(session, question, questions_precedentes, categories)
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
    texte, contact_sav = separer_contact_sav(texte)
    sources = references_citees(texte, preparation.references)
    ajouter_message(session, conversation, "user", preparation.question)
    message = ajouter_message(session, conversation, "assistant", texte, sources=[asdict(source) for source in sources],
                              modele_llm=consommation.modele if consommation else None,
                              tokens_entree=consommation.tokens_entree if consommation else None,
                              tokens_sortie=consommation.tokens_sortie if consommation else None,
                              cout=consommation.cout if consommation else None, contact_sav=contact_sav)
    return ReponseAssistant(texte=texte, sources=sources, message=message, consommation=consommation, contact_sav=contact_sav)


def repondre(session : Session, conversation : Conversation, question : str, categories : list[str] | None = None) -> ReponseAssistant :
    """réponse complète (sans streaming), enregistrée dans la conversation"""
    preparation = preparer(session, question, historique_conversation(session, conversation), categories)
    if preparation.messages is None :
        return enregistrer_echange(session, conversation, preparation, preparation.reponse_directe)
    reponse = completer(preparation.messages)
    return enregistrer_echange(session, conversation, preparation, reponse.texte, reponse.consommation)
