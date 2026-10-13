"""lecture des documents structurés (pdf, docx, html générique) avec Docling.

étapes : conversion (avec cache) -> réparation du document -> découpage en chunks.
les réparations corrigent ce que la conversion abîme :
- titre du document isolé de la couverture (il sera remis en contexte de chaque chunk par data.py)
- niveaux des titres numérotés (les pdf arrivent a plat : "2.3" devient un sous-titre de "2.")
- tableaux coupés par un saut de page recollés (sinon une ligne coupée devient l'en-tête des colonnes)
- bruit retiré (sommaire, mentions de rédaction)
"""
import hashlib
import logging
import re
import time
from functools import lru_cache
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ContentLayer, DoclingDocument, NodeItem, SectionHeaderItem, TableItem, TextItem

from backend.chargement.chunker import creer_chunker
from backend.chargement.schemas import ChunkLu, DocumentLu

logger = logging.getLogger(__name__)

RE_NUMERO_TITRE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s")             # "2. Installation", "2.3 Raccordement"
TITRES_SANS_CONTENU_UTILE = {"sommaire", "table des matières"}
RE_BRUIT = re.compile(r"^Rédaction\s*:")                             # pied de page des documents internes
RE_MARQUE = re.compile(r"^ELECTRODOMUS\b\s*(?:—\s*)?", re.IGNORECASE)
LIGNES_GENERIQUES = {"", "documentation interne"}
NB_ITEMS_ENTETE = 8                                                  # items du début gardés pour chercher la version
RE_GRAS = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
RE_ITALIQUE = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", re.DOTALL)
RE_CARACTERES_PRIVES = re.compile(r"[-]")                 # puces des polices Symbol des pdf (U+F0B7...)
RE_DOUBLE_POINT = re.compile(r"(?<!\.)\.\.(?!\.)")                   # "texte.." : point de la cellule + point ajouté par la sérialisation des tableaux


## CONVERSION ##

@lru_cache
def _convertisseur() -> DocumentConverter :
    # pdf numériques : le texte est déjà dans le fichier, l'OCR ralentit sans rien apporter
    options_pdf = PdfPipelineOptions(do_ocr=False)
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options_pdf)})


def convertir(chemin : Path, dossier_cache : Path | None = None) -> DoclingDocument :
    """convertit le fichier en DoclingDocument. si dossier_cache est donné, le résultat y est gardé
    (clé = contenu du fichier) : la conversion d'un pdf prend ~30 s, le cache évite de la refaire a chaque essai de découpage"""
    cache = None
    if dossier_cache is not None :
        empreinte = hashlib.sha1(chemin.read_bytes()).hexdigest()[:16]
        cache = dossier_cache / f"{chemin.stem}-{empreinte}.json"
        if cache.exists() :
            logger.debug("%s : conversion lue depuis le cache", chemin.name)
            return DoclingDocument.load_from_json(cache)

    debut = time.perf_counter()
    document = _convertisseur().convert(chemin).document
    logger.info("%s converti en %.1f s", chemin.name, time.perf_counter() - debut)

    if cache is not None :
        dossier_cache.mkdir(parents=True, exist_ok=True)
        document.save_as_json(cache)
    return document


## RÉPARATIONS ##

def _masquer(items : list[NodeItem]) -> None :
    """sort les items du corps du document : le chunker ne les découpe plus"""
    for item in items :
        item.content_layer = ContentLayer.FURNITURE


def _items_corps(document : DoclingDocument) -> list[NodeItem] :
    return [item for item, _ in document.iterate_items()]


def _page(item : NodeItem) -> int | None :
    prov = getattr(item, "prov", None)
    return prov[0].page_no if prov else None


def _sans_marque(texte : str) -> str :
    return RE_MARQUE.sub("", texte).strip()


def _extraire_couverture(document : DoclingDocument) -> tuple[str | None, str] :
    """renvoie (titre, entete) et masque le bloc de couverture.
    - pdf : les titres empilés en haut de la page 1 (hors marque seule), sauf le dernier qui porte le texte qui suit
      (exception : s'il n'y en a qu'un, c'est le titre du document)
    - docx : les paragraphes avant le premier titre de section ; le titre = les lignes en gras"""
    items = _items_corps(document)
    entete = "\n".join(item.text for item in items[:NB_ITEMS_ENTETE] if isinstance(item, TextItem))

    if document.pages :
        pile = []
        for item in items :
            if not isinstance(item, SectionHeaderItem) or _page(item) != 1 :
                break
            pile.append(item)
        # la marque seule ("ELECTRODOMUS") ne compte pas : selon la mise en page elle est un titre a part ou non
        marque = [item for item in pile if _sans_marque(item.text).lower() in LIGNES_GENERIQUES]
        titres = [item for item in pile if all(item is not autre for autre in marque)]
        titres = titres if len(titres) <= 1 else titres[:-1]
        couverture = marque + titres
        lignes = [item.text for item in titres]
    else :
        couverture = []
        for item in items :
            if isinstance(item, SectionHeaderItem) :
                break
            couverture.append(item)
        textes = [item for item in couverture if isinstance(item, TextItem)]
        lignes = [item.text for item in textes if item.formatting is not None and item.formatting.bold]

    parties = [_sans_marque(ligne) for ligne in lignes]
    parties = [partie for partie in parties if partie.lower() not in LIGNES_GENERIQUES]
    _masquer(couverture)
    return (" — ".join(parties) or None), entete


def _fixer_niveaux_titres(document : DoclingDocument) -> None :
    """"2.3 Raccordement" -> niveau 2 : le chunker garde alors le chemin "2. Installation > 2.3 Raccordement" """
    for item in _items_corps(document) :
        if isinstance(item, SectionHeaderItem) :
            numero = RE_NUMERO_TITRE.match(item.text)
            if numero :
                item.level = numero.group(1).count(".") + 1


def _est_suite_de(tableau : TableItem, suite : TableItem) -> bool :
    """un tableau qui suit directement un autre sur la page suivante, avec le même nombre de colonnes
    et sans vraie ligne d'en-tête, est la suite du premier coupée par le saut de page"""
    page_fin, page_suite = tableau.prov[-1].page_no if tableau.prov else None, _page(suite)
    if page_fin is None or page_suite != page_fin + 1 or tableau.data.num_cols != suite.data.num_cols :
        return False
    return not all(cellule.column_header for cellule in suite.data.grid[0])


def _recoller(tableau : TableItem, suite : TableItem) -> None :
    """ajoute les lignes de suite a la fin de tableau.
    si la 1re cellule de la suite est vide, cette ligne est la fin de la dernière ligne du tableau : on la recolle dedans"""
    donnees, lignes_suite = tableau.data, suite.data.grid
    debut = 0
    if not lignes_suite[0][0].text.strip() :
        derniere = donnees.num_rows - 1
        for morceau in lignes_suite[0] :
            if not morceau.text.strip() :
                continue
            for cellule in donnees.table_cells :
                if cellule.start_row_offset_idx <= derniere < cellule.end_row_offset_idx \
                        and cellule.start_col_offset_idx <= morceau.start_col_offset_idx < cellule.end_col_offset_idx :
                    cellule.text = f"{cellule.text} {morceau.text}".strip()
        debut = 1

    decalage = donnees.num_rows - debut
    for cellule in suite.data.table_cells :
        if cellule.start_row_offset_idx >= debut :
            donnees.table_cells.append(cellule.model_copy(update={
                "start_row_offset_idx": cellule.start_row_offset_idx + decalage,
                "end_row_offset_idx": cellule.end_row_offset_idx + decalage,
                "column_header": False,
            }))
    donnees.num_rows += suite.data.num_rows - debut
    tableau.prov.extend(suite.prov)


def _recoller_tableaux_coupes(document : DoclingDocument, nom : str) -> None :
    a_supprimer = []
    precedent = None
    for item in _items_corps(document) :
        if isinstance(item, TableItem) and isinstance(precedent, TableItem) and _est_suite_de(precedent, item) :
            _recoller(precedent, item)
            a_supprimer.append(item)
            logger.debug("%s : tableau page %s recollé au précédent", nom, _page(item))
            continue        # precedent reste le tableau complété (cas d'un tableau sur 3 pages)
        precedent = item
    if a_supprimer :
        document.delete_items(node_items=a_supprimer)
        logger.info("%s : %d tableau(x) coupé(s) par un saut de page recollé(s)", nom, len(a_supprimer))


def _masquer_bruit(document : DoclingDocument) -> None :
    """masque le sommaire (titre + contenu jusqu'au titre suivant) et les mentions de rédaction"""
    bruit, dans_sommaire = [], False
    for item in _items_corps(document) :
        if isinstance(item, SectionHeaderItem) :
            dans_sommaire = item.text.strip().lower() in TITRES_SANS_CONTENU_UTILE
        if dans_sommaire or (isinstance(item, TextItem) and RE_BRUIT.match(item.text)) :
            bruit.append(item)
    _masquer(bruit)


## DÉCOUPAGE ##

def _nettoyer(texte : str) -> str :
    """retire le gras / italique markdown ajouté par la sérialisation, les caractères parasites et les espaces en trop"""
    texte = RE_ITALIQUE.sub(r"\1", RE_GRAS.sub(r"\1", texte))
    texte = RE_DOUBLE_POINT.sub(".", RE_CARACTERES_PRIVES.sub("", texte))
    lignes = (re.sub(r"[^\S\n]+", " ", ligne).strip() for ligne in texte.splitlines())
    return "\n".join(ligne for ligne in lignes if ligne)


def lire_document_docling(chemin : Path, dossier_cache : Path | None = None) -> DocumentLu :
    """convertit, répare et découpe un document"""
    document = convertir(chemin, dossier_cache)
    titre, entete = _extraire_couverture(document)
    _fixer_niveaux_titres(document)
    _recoller_tableaux_coupes(document, chemin.name)
    _masquer_bruit(document)

    chunks = []
    for chunk in creer_chunker().chunk(dl_doc=document) :
        texte = _nettoyer(chunk.text)
        if not texte :
            continue
        pages = sorted({prov.page_no for item in chunk.meta.doc_items for prov in item.prov})
        chunks.append(ChunkLu(texte=texte, titres=list(chunk.meta.headings or []), pages=pages))

    if titre is None :
        logger.warning("%s : titre introuvable dans le document", chemin.name)
    return DocumentLu(titre=titre, entete=entete, chunks=chunks)
