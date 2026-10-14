"""aperçu HTML des docx, xlsx et html pour le lecteur (les pdf sont servis tels quels).
sans base ni Docling ; le front nettoie de toute façon le HTML (DOMPurify)"""
import html
import logging
import time
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from docx import Document as DocumentWord
from docx.table import Table
from docx.text.paragraph import Paragraph

from backend.config import DOCS

logger = logging.getLogger(__name__)

FORMATS_APERCU = {".docx", ".xlsx", ".html"}
BALISES_TITRE = {"Title": "h1", "Heading 1": "h2", "Heading 2": "h3", "Heading 3": "h4"}     # styles Word -> balises
BALISES_LISTE = {"List Bullet": "ul", "List Number": "ol"}
BALISES_RETIREES = ["script", "style", "link", "meta", "noscript", "iframe", "object", "embed", "form"]


class DocumentIntrouvable(Exception) :
    """la source sort du dossier de documentation, ou son fichier n'existe pas"""


def chemin_du_document(source : str) -> Path :
    """chemin du fichier d'une source (chemin relatif au dossier de documentation, cf. data.source_du_fichier).
    refuse toute source qui sortirait du dossier ("../.env")"""
    racine = DOCS.resolve()
    chemin = (racine / source).resolve()
    if not chemin.is_relative_to(racine) or not chemin.is_file() :
        raise DocumentIntrouvable(source)
    return chemin


def _tableau(lignes : list[list[str]]) -> str :
    """tableau HTML ; la 1re ligne est l'en-tête"""
    if not lignes :
        return ""
    entete = "".join(f"<th>{html.escape(cellule)}</th>" for cellule in lignes[0])
    corps = "".join("<tr>" + "".join(f"<td>{html.escape(cellule)}</td>" for cellule in ligne) + "</tr>" for ligne in lignes[1:])
    return f"<table><thead><tr>{entete}</tr></thead><tbody>{corps}</tbody></table>"


## DOCX ##

def _texte_mis_en_forme(paragraphe : Paragraph) -> str :
    morceaux = []
    for run in paragraphe.runs :
        texte = html.escape(run.text)
        if not texte :
            continue
        if run.italic :
            texte = f"<em>{texte}</em>"
        if run.bold :
            texte = f"<strong>{texte}</strong>"
        morceaux.append(texte)
    return "".join(morceaux)


def _docx(chemin : Path) -> str :
    parties, liste_ouverte = [], None
    for bloc in DocumentWord(str(chemin)).iter_inner_content() :
        style = bloc.style.name if isinstance(bloc, Paragraph) and bloc.style is not None else ""
        balise_liste = BALISES_LISTE.get(style)
        if liste_ouverte and balise_liste != liste_ouverte :        # fin de la liste en cours
            parties.append(f"</{liste_ouverte}>")
            liste_ouverte = None
        if isinstance(bloc, Table) :
            parties.append(_tableau([[cellule.text.strip() for cellule in ligne.cells] for ligne in bloc.rows]))
            continue
        contenu = _texte_mis_en_forme(bloc)
        if not contenu.strip() :
            continue
        if balise_liste :
            if liste_ouverte is None :
                parties.append(f"<{balise_liste}>")
                liste_ouverte = balise_liste
            parties.append(f"<li>{contenu}</li>")
        else :
            balise = BALISES_TITRE.get(style, "p")
            parties.append(f"<{balise}>{contenu}</{balise}>")
    if liste_ouverte :
        parties.append(f"</{liste_ouverte}>")
    return "\n".join(parties)


## XLSX ##

def _xlsx(chemin : Path) -> str :
    """un onglet = son nom, ses lignes d'une seule cellule (titre, version) en paragraphes, puis son tableau"""
    parties = []
    for nom, feuille in pd.read_excel(chemin, sheet_name=None, header=None).items() :
        feuille = feuille.dropna(how="all").dropna(axis=1, how="all")
        parties.append(f"<h2>{html.escape(str(nom))}</h2>")
        tableau = []
        for ligne in feuille.itertuples(index=False) :
            cellules = ["" if pd.isna(valeur) else str(valeur).strip() for valeur in ligne]
            if sum(1 for cellule in cellules if cellule) > 1 :
                tableau.append(cellules)
                continue
            if tableau :                                  # une ligne isolée après un tableau le termine
                parties.append(_tableau(tableau))
                tableau = []
            parties.append(f"<p>{html.escape(next(cellule for cellule in cellules if cellule))}</p>")
        parties.append(_tableau(tableau))
    return "\n".join(partie for partie in parties if partie)


## HTML ##

def _html(chemin : Path) -> str :
    soupe = BeautifulSoup(chemin.read_text(encoding="utf-8"), "lxml")
    for element in soupe(BALISES_RETIREES) :
        element.decompose()
    principal = soupe.find("main") or soupe.body or soupe
    for balise in principal.find_all(True) :
        for attribut in [nom for nom in balise.attrs if nom.lower().startswith("on")] :     # onclick, onload...
            del balise[attribut]
    return principal.decode_contents()


LECTEURS = {".docx" : _docx, ".xlsx" : _xlsx, ".html" : _html}


def apercu_html(chemin : Path) -> str :
    """aperçu HTML d'un document docx, xlsx ou html ; lève ValueError pour un autre format (pdf)"""
    lecteur = LECTEURS.get(chemin.suffix.lower())
    if lecteur is None :
        raise ValueError(f"pas d'aperçu HTML pour le format {chemin.suffix}")
    debut = time.perf_counter()
    resultat = lecteur(chemin)
    logger.debug("aperçu de %s en %.0f ms", chemin.name, (time.perf_counter() - debut) * 1000)
    return resultat
