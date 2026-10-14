"""chargement de la documentation (lecture, découpage, métadonnées), sans base.
python -m backend.chargement.data écrit assets/chunks.json pour contrôle"""
import hashlib
import json
import logging
import re
import time
from dataclasses import asdict
from pathlib import Path

from backend.config import ASSETS, CATEGORIE_PAR_DEFAUT, CATEGORIE_REFERENTIEL, CATEGORIES_PAR_DOSSIER, DOCS, MODELE_EMBEDDING
from backend.chargement.chunker import MAX_TOKENS_CHUNK, TOKENS_RESERVES_CONTEXTE, compter_tokens
from backend.chargement.lecture_docling import lire_document_docling
from backend.chargement.lecture_excel import lire_referentiel
from backend.chargement.lecture_html import lire_faq_html
from backend.chargement.schemas import ChunkCharge, ChunkLu, DocumentCharge, DocumentLu, Referentiel

logger = logging.getLogger(__name__)

EXTENSIONS = {".pdf", ".docx", ".html"}
FICHIER_REFERENTIEL = DOCS / "Referentiel_codes_erreur.xlsx"
DOSSIER_CACHE = ASSETS / "cache_docling"
FICHIER_EXPORT = ASSETS / "chunks.json"
# a changer quand les règles de lecture ou de découpage changent : toutes les empreintes changent,
# la prochaine ingestion retraite donc tous les documents (cf. empreinte_du_fichier)
VERSION_DECOUPAGE = "2026-10-14"

# préfixe de gamme -> type d'appareil (cf. onglets du référentiel des codes erreur)
GAMMES = {"WX": "lave-linge", "LV": "lave-vaisselle", "FR": "four"}

_PREFIXES = "|".join(GAMMES)
RE_MODELE = re.compile(rf"\b(?:{_PREFIXES})-\d{{3}}\b")                                    # WX-500
RE_GAMME = re.compile(rf"\b(?i:gamme|modèles|série|serie)\s+(?:[\w-]+\s+)?({_PREFIXES})\b(?!-)")   # gamme LV, Gamme lave-linge WX
RE_CODE_ERREUR = re.compile(r"\bE\d{2}\b")
RE_MODELES_CONCERNES = re.compile(r"(?i:modèles concernés)\s*:\s*([^\n]*)")
RE_PARENTHESES = re.compile(r"\([^)]*\)")
RES_VERSION = [
    re.compile(r"(?i:édition)\s+((?:\w+\s+)?\d{4})"),          # Édition 2024, édition janvier 2026
    re.compile(r"(?i:diffusé le)\s+(\d{1,2} \w+ \d{4})"),      # bulletins techniques
    re.compile(r"(?i:mise à jour le)\s+(\d{1,2} \w+ \d{4})"),  # FAQ
]


## MÉTADONNÉES ##

def _extraire_version(texte : str) -> str | None :
    for regex in RES_VERSION :
        trouve = regex.search(texte)
        if trouve :
            return trouve.group(1)
    return None


def _perimetre_declare(chunks : list[ChunkLu]) -> str | None :
    """texte de la rubrique "Modèles concernés" du document (procédures, fiches de garantie), sans les parenthèses
    qui portent des précisions ou des exclusions : "FR-700, FR-750 (les FR-600 et FR-650 ne sont pas équipés)" """
    for chunk in chunks :
        if any("modèles concernés" in titre.lower() for titre in chunk.titres) :
            return RE_PARENTHESES.sub("", chunk.texte)
        trouve = RE_MODELES_CONCERNES.search(chunk.texte)
        if trouve :
            return RE_PARENTHESES.sub("", trouve.group(1))
    return None


def _modeles_du_document(titre : str, nom_fichier : str, chunks : list[ChunkLu]) -> tuple[set[str], set[str]] :
    """modèles et gammes du document : rubrique « Modèles concernés », sinon titre et nom du fichier,
    sinon type d'appareil du titre ; rien = document général (CGV), valable pour tous"""
    perimetre = _perimetre_declare(chunks)
    if perimetre is not None :
        modeles, gammes = set(RE_MODELE.findall(perimetre)), set(RE_GAMME.findall(perimetre))
        if modeles or gammes :
            return modeles, gammes

    texte = f"{titre} {nom_fichier.replace('_', ' ')}"
    modeles, gammes = set(RE_MODELE.findall(texte)), set(RE_GAMME.findall(texte))
    if not modeles and not gammes :
        gammes = {gamme for gamme, appareil in GAMMES.items() if re.search(rf"\b{appareil}s?\b", texte, re.IGNORECASE)}
    return modeles, gammes


def _construire_chunk(position : int, lu : ChunkLu, prefixe : str, modeles : set[str], gammes : set[str]) -> ChunkCharge :
    """ajoute au texte son contexte (document + titres de section) : sans lui, "2.3 Raccordement en eau"
    est identique dans les 6 manuels WX et la recherche ne peut pas les distinguer"""
    contexte = [prefixe] + ([" > ".join(lu.titres)] if lu.titres else [])
    contenu = "\n".join(contexte + [lu.texte])
    return ChunkCharge(
        position=position,
        contenu=contenu,
        texte=lu.texte,
        titres=lu.titres,
        pages=lu.pages,
        modeles=sorted(modeles | set(RE_MODELE.findall(lu.texte))),
        gammes=sorted(gammes | set(RE_GAMME.findall(lu.texte))),
        codes_erreur=sorted(set(RE_CODE_ERREUR.findall(contenu))),
    )


## CHARGEMENT ##

def source_du_fichier(chemin : Path) -> str :
    """identifiant stable du fichier : son chemin relatif au dossier de documentation"""
    return chemin.relative_to(DOCS).as_posix() if chemin.is_relative_to(DOCS) else chemin.name


def empreinte_du_fichier(chemin : Path) -> str :
    """sha256 du contenu du fichier et de la façon de le traiter (version du découpage, modèle d'embedding) :
    elle change si le fichier change, mais aussi si les chunks ou leurs vecteurs seraient calculés autrement"""
    empreinte = hashlib.sha256(f"{VERSION_DECOUPAGE}|{MODELE_EMBEDDING}|".encode("utf-8"))
    empreinte.update(chemin.read_bytes())
    return empreinte.hexdigest()


def lister_fichiers(dossier : Path = DOCS) -> list[Path] :
    """documents a charger (hors référentiel excel et fichiers temporaires office ~$...)"""
    return sorted(chemin for chemin in dossier.rglob("*")
                  if chemin.is_file() and not chemin.name.startswith("~$") and chemin.suffix.lower() in EXTENSIONS)


def _lire(chemin : Path) -> DocumentLu :
    if chemin.suffix.lower() == ".html" :
        lu = lire_faq_html(chemin)
        if lu.chunks :
            return lu
        logger.info("%s : pas de structure FAQ, lecture par Docling", chemin.name)
    return lire_document_docling(chemin, dossier_cache=DOSSIER_CACHE)


def charger_document(chemin : Path) -> DocumentCharge :
    """lit, découpe et enrichit un document"""
    lu = _lire(chemin)
    type_document = CATEGORIES_PAR_DOSSIER.get(chemin.parent.name, CATEGORIE_PAR_DEFAUT)
    titre = lu.titre or chemin.stem.replace("_", " ")
    prefixe = f"[{type_document}] {titre}"
    if compter_tokens(prefixe) > TOKENS_RESERVES_CONTEXTE :
        logger.warning("%s : contexte de %d tokens, plus que les %d réservés", chemin.name, compter_tokens(prefixe), TOKENS_RESERVES_CONTEXTE)

    modeles, gammes = _modeles_du_document(titre, chemin.stem, lu.chunks)
    chunks = [_construire_chunk(position, chunk, prefixe, modeles, gammes) for position, chunk in enumerate(lu.chunks)]
    for chunk in chunks :
        if compter_tokens(chunk.contenu) > MAX_TOKENS_CHUNK :
            logger.warning("%s : chunk %d trop long (%d tokens)", chemin.name, chunk.position, compter_tokens(chunk.contenu))

    return DocumentCharge(source=source_du_fichier(chemin), type_document=type_document, titre=titre,
                          version=_extraire_version(f"{lu.entete}\n{titre}"),
                          modeles=sorted(modeles), gammes=sorted(gammes), chunks=chunks)


def charger_documents(fichiers : list[Path]) -> list[DocumentCharge] :
    """charge tous les fichiers ; un fichier en échec est journalisé puis ignoré, les autres continuent"""
    documents, echecs = [], []
    debut = time.perf_counter()
    for chemin in fichiers :
        try :
            document = charger_document(chemin)
        except Exception :
            logger.exception("échec du chargement de %s", chemin.name)
            echecs.append(chemin.name)
            continue
        logger.info("%s : %d chunks (titre : %s | version : %s | modèles : %s | gammes : %s)", chemin.name, len(document.chunks),
                    document.titre, document.version, document.modeles or "-", document.gammes or "-")
        documents.append(document)

    logger.info("%d documents chargés, %d chunks, %d échec(s) en %.0f s", len(documents),
                sum(len(document.chunks) for document in documents), len(echecs), time.perf_counter() - debut)
    if echecs :
        logger.warning("fichiers en échec : %s", ", ".join(echecs))
    return documents


## RÉFÉRENTIEL DES CODES ERREUR ##

def charger_referentiel(chemin : Path = FICHIER_REFERENTIEL) -> Referentiel :
    return lire_referentiel(chemin, source=source_du_fichier(chemin))


def document_du_referentiel(referentiel : Referentiel) -> DocumentCharge :
    """un chunk par code erreur et par gamme, pour que la recherche retrouve aussi le référentiel.
    les modèles et le code viennent des colonnes du tableau : pas besoin de les deviner dans le texte"""
    titre = "Référentiel des codes erreur" + (f" (version {referentiel.version})" if referentiel.version else "")
    prefixe = f"[{CATEGORIE_REFERENTIEL}] {titre}"
    chunks = []
    for position, erreur in enumerate(referentiel.erreurs) :
        section = f"{erreur.type_appareil} série {erreur.gamme}"
        texte = "\n".join([
            f"{erreur.code} — {erreur.signification}",
            f"Conduite à tenir (client) : {erreur.conduite}",
            f"Intervention SAV (technicien) : {erreur.intervention}",
            f"Modèles concernés : {', '.join(erreur.modeles)}",
        ])
        chunks.append(ChunkCharge(position=position, contenu="\n".join([prefixe, section, texte]), texte=texte,
                                  titres=[section], pages=[], modeles=sorted(erreur.modeles), gammes=[],
                                  codes_erreur=[erreur.code]))

    modeles = sorted({modele for erreur in referentiel.erreurs for modele in erreur.modeles})
    return DocumentCharge(source=referentiel.source, type_document=CATEGORIE_REFERENTIEL, titre=titre,
                          version=referentiel.version, modeles=modeles, gammes=[], chunks=chunks)


## EXPORT ##

def exporter_json(documents : list[DocumentCharge], chemin : Path = FICHIER_EXPORT) -> None :
    """écrit les documents et leurs chunks en json, pour les relire / contrôler"""
    with open(chemin, "w", encoding="utf-8") as fichier :
        json.dump([asdict(document) for document in documents], fichier, indent=2, ensure_ascii=False)
    logger.info("export écrit dans %s", chemin)


if __name__ == "__main__" :
    from logger import configurer_logs

    configurer_logs()
    exporter_json([document_du_referentiel(charger_referentiel())] + charger_documents(lister_fichiers()))
