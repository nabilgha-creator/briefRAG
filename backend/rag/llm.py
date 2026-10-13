"""appel du LLM via OpenRouter (API compatible OpenAI), avec httpx : pas de SDK supplémentaire.
ne dépend ni de la base de données ni du reste du projet.

réglages dans le .env :
- CLE_OPENR : clé API OpenRouter (obligatoire)
- MODELE_LLM : modèle OpenRouter (défaut anthropic/claude-haiku-4.5 : 1 $ / 5 $ par million de tokens entrée / sortie)
"""
import json
import logging
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

URL_OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
VARIABLE_CLE = "CLE_OPENR"
MODELE_PAR_DEFAUT = "anthropic/claude-haiku-4.5"
TEMPERATURE = 0.2               # réponses factuelles : peu de variabilité
MAX_TOKENS_REPONSE = 900        # plafond de la réponse, donc du coût de sortie
DELAIS = httpx.Timeout(60.0, connect=10.0)
NB_ESSAIS = 3
STATUTS_A_REESSAYER = {408, 429, 500, 502, 503, 504}


class ErreurLLM(RuntimeError) :
    """l'appel au LLM a échoué (clé absente, refus, réseau...) ; le message est affichable"""


@dataclass
class Consommation :
    modele : str
    tokens_entree : int | None = None
    tokens_sortie : int | None = None
    cout : float | None = None          # en dollars, renvoyé par OpenRouter


@dataclass
class ReponseLLM :
    texte : str
    consommation : Consommation


def modele_llm() -> str :
    return os.getenv("MODELE_LLM", MODELE_PAR_DEFAUT)


def _entetes() -> dict[str, str] :
    cle = os.getenv(VARIABLE_CLE)
    if not cle :
        raise ErreurLLM(f"clé API absente : ajoutez {VARIABLE_CLE}=... dans le fichier .env")
    return {"Authorization": f"Bearer {cle}", "X-Title": "BriefRAG"}


def _corps(messages : list[dict[str, str]], flux : bool) -> dict :
    return {"model": modele_llm(), "messages": messages, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS_REPONSE,
            "stream": flux, "usage": {"include": True}}


def _message_erreur(reponse : httpx.Response) -> str :
    try :
        return reponse.json()["error"]["message"]
    except (ValueError, KeyError, TypeError) :
        return reponse.text[:300]


def _consommation(donnees : dict) -> Consommation :
    usage = donnees.get("usage") or {}
    return Consommation(modele=donnees.get("model", modele_llm()), tokens_entree=usage.get("prompt_tokens"),
                        tokens_sortie=usage.get("completion_tokens"), cout=usage.get("cost"))


def _journaliser(consommation : Consommation, debut : float) -> None :
    logger.info("LLM %s : %s tokens en entrée, %s en sortie, coût %s $, %.1f s", consommation.modele, consommation.tokens_entree,
                consommation.tokens_sortie, consommation.cout, time.perf_counter() - debut)


def _attendre_avant_nouvel_essai(essai : int, raison : str) -> None :
    attente = 2 ** essai
    logger.warning("OpenRouter : %s, nouvel essai dans %d s (%d/%d)", raison, attente, essai, NB_ESSAIS)
    time.sleep(attente)


def completer(messages : list[dict[str, str]]) -> ReponseLLM :
    """réponse complète en un seul appel"""
    debut = time.perf_counter()
    for essai in range(1, NB_ESSAIS + 1) :
        try :
            reponse = httpx.post(URL_OPENROUTER, json=_corps(messages, flux=False), headers=_entetes(), timeout=DELAIS)
        except httpx.TransportError as erreur :
            if essai == NB_ESSAIS :
                raise ErreurLLM(f"OpenRouter injoignable : {erreur}") from erreur
            _attendre_avant_nouvel_essai(essai, f"erreur réseau ({erreur})")
            continue
        if reponse.status_code in STATUTS_A_REESSAYER and essai < NB_ESSAIS :
            _attendre_avant_nouvel_essai(essai, f"statut {reponse.status_code}")
            continue
        if reponse.status_code != 200 :
            raise ErreurLLM(f"OpenRouter a refusé la requête ({reponse.status_code}) : {_message_erreur(reponse)}")

        donnees = reponse.json()
        if "error" in donnees :
            raise ErreurLLM(f"erreur du modèle : {donnees['error'].get('message')}")
        consommation = _consommation(donnees)
        _journaliser(consommation, debut)
        return ReponseLLM(texte=donnees["choices"][0]["message"]["content"] or "", consommation=consommation)
    raise ErreurLLM("OpenRouter : nombre d'essais dépassé")


class FluxLLM :
    """réponse au fil de l'eau : on itère sur les morceaux de texte ; la consommation est connue a la fin du flux.
    les nouveaux essais n'ont lieu qu'avant le premier morceau (ensuite le texte a déjà été envoyé a l'utilisateur)"""

    def __init__(self, messages : list[dict[str, str]]) -> None :
        self.messages = messages
        self.consommation = Consommation(modele=modele_llm())

    def __iter__(self) -> Iterator[str] :
        debut = time.perf_counter()
        for essai in range(1, NB_ESSAIS + 1) :
            try :
                with httpx.stream("POST", URL_OPENROUTER, json=_corps(self.messages, flux=True), headers=_entetes(), timeout=DELAIS) as reponse :
                    if reponse.status_code in STATUTS_A_REESSAYER and essai < NB_ESSAIS :
                        _attendre_avant_nouvel_essai(essai, f"statut {reponse.status_code}")
                        continue
                    if reponse.status_code != 200 :
                        reponse.read()
                        raise ErreurLLM(f"OpenRouter a refusé la requête ({reponse.status_code}) : {_message_erreur(reponse)}")
                    yield from self._lire(reponse)
                    _journaliser(self.consommation, debut)
                    return
            except httpx.TransportError as erreur :
                if essai == NB_ESSAIS :
                    raise ErreurLLM(f"OpenRouter injoignable : {erreur}") from erreur
                _attendre_avant_nouvel_essai(essai, f"erreur réseau ({erreur})")

    def _lire(self, reponse : httpx.Response) -> Iterator[str] :
        """lignes server-sent events : "data: {...}" ... "data: [DONE]" ; les lignes ":" sont des commentaires"""
        for ligne in reponse.iter_lines() :
            if not ligne.startswith("data: ") :
                continue
            charge = ligne[len("data: "):]
            if charge == "[DONE]" :
                break
            donnees = json.loads(charge)
            if "error" in donnees :
                raise ErreurLLM(f"erreur du modèle : {donnees['error'].get('message')}")
            if donnees.get("usage") :
                self.consommation = _consommation(donnees)
            for choix in donnees.get("choices", []) :
                morceau = (choix.get("delta") or {}).get("content")
                if morceau :
                    yield morceau
