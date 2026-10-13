"""lecture des pages FAQ html avec BeautifulSoup : un chunk par question / réponse.

Docling lit bien ces pages mais regroupe toutes les questions d'une section dans un seul chunk :
le vecteur mélange alors 4 a 6 sujets et la recherche perd en précision.
structure attendue : <section> avec un <h2>, puis des <details><summary>question</summary>réponse</details>
"""
import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from backend.chargement.schemas import ChunkLu, DocumentLu

logger = logging.getLogger(__name__)

BLOCS_TEXTE = ["p", "li", "td"]


def _texte(element : Tag) -> str :
    return re.sub(r"\s+", " ", element.get_text(" ", strip=True))


def _reponse(details : Tag) -> str :
    """texte de la réponse, un paragraphe / élément de liste par ligne"""
    blocs = [_texte(bloc) for bloc in details.find_all(BLOCS_TEXTE)]
    blocs = [bloc for bloc in blocs if bloc]
    return "\n".join(blocs) if blocs else _texte(details)


def lire_faq_html(chemin : Path) -> DocumentLu :
    """renvoie les questions / réponses de la page. aucun chunk si la page n'a pas la structure FAQ attendue"""
    soupe = BeautifulSoup(chemin.read_text(encoding="utf-8"), "lxml")
    principal = soupe.find("main") or soupe.body or soupe

    h1 = principal.find("h1")
    titre = _texte(h1) if h1 else None
    mise_a_jour = principal.find(class_="updated")
    entete = _texte(mise_a_jour) if mise_a_jour else ""

    chunks = []
    for details in principal.find_all("details") :
        question = details.find("summary")
        if question is None :
            logger.warning("%s : bloc <details> sans question ignoré", chemin.name)
            continue
        texte_question = _texte(question)
        question.extract()          # la question ne doit pas se retrouver dans la réponse
        texte_reponse = _reponse(details)
        if not texte_reponse :
            logger.warning("%s : question sans réponse ignorée : %s", chemin.name, texte_question)
            continue

        section = details.find_parent("section")
        h2 = section.find("h2") if section else None
        chunks.append(ChunkLu(texte=f"Question : {texte_question}\nRéponse : {texte_reponse}",
                              titres=[_texte(h2)] if h2 else []))

    logger.debug("%s : %d questions / réponses lues", chemin.name, len(chunks))
    return DocumentLu(titre=titre, entete=entete, chunks=chunks)
