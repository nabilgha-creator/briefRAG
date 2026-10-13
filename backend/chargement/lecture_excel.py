"""lecture du référentiel excel des codes erreur : un onglet par gamme.

structure attendue d'un onglet :
- 1re ligne : titre "Référentiel des codes erreur — Lave-linge serie WX" (type d'appareil + gamme)
- une ligne "Version 2025-T4 ..." avant le tableau
- une ligne d'en-tête qui commence par "Code", puis une ligne par code erreur
"""
import logging
import re
from pathlib import Path

import pandas as pd

from backend.chargement.schemas import ErreurReferentiel, Referentiel

logger = logging.getLogger(__name__)

RE_TITRE_ONGLET = re.compile(r"—\s*(?P<type>.+?)\s+s[ée]rie\s+(?P<gamme>[A-Z]+)\s*$", re.IGNORECASE)
RE_VERSION = re.compile(r"Version\s+(\S+)", re.IGNORECASE)

# en-tête de colonne (début, en minuscules) -> champ de ErreurReferentiel
COLONNES = {
    "code": "code",
    "signification": "signification",
    "conduite": "conduite",
    "intervention": "intervention",
    "modèles": "modeles",
}


def _texte(valeur : object) -> str :
    return "" if pd.isna(valeur) else re.sub(r"\s+", " ", str(valeur)).strip()


def _lire_onglet(feuille : pd.DataFrame, nom_onglet : str) -> tuple[list[ErreurReferentiel], str | None] :
    titre = _texte(feuille.iat[0, 0])
    trouve = RE_TITRE_ONGLET.search(titre)
    if trouve is None :
        raise ValueError(f"onglet {nom_onglet} : titre inattendu {titre!r} (type d'appareil et gamme introuvables)")
    type_appareil, gamme = trouve["type"], trouve["gamme"].upper()

    version, ligne_entete = None, None
    for index in range(len(feuille)) :
        premiere = _texte(feuille.iat[index, 0])
        if version is None and (trouve_version := RE_VERSION.match(premiere)) :
            version = trouve_version.group(1)
        if premiere.lower() == "code" :
            ligne_entete = index
            break
    if ligne_entete is None :
        raise ValueError(f"onglet {nom_onglet} : ligne d'en-tête 'Code' introuvable")

    positions = {}
    for colonne in range(feuille.shape[1]) :
        entete = _texte(feuille.iat[ligne_entete, colonne]).lower()
        for debut, champ in COLONNES.items() :
            if entete.startswith(debut) :
                positions[champ] = colonne
    manquantes = set(COLONNES.values()) - set(positions)
    if manquantes :
        raise ValueError(f"onglet {nom_onglet} : colonnes manquantes {sorted(manquantes)}")

    erreurs = []
    for index in range(ligne_entete + 1, len(feuille)) :
        valeurs = {champ : _texte(feuille.iat[index, colonne]) for champ, colonne in positions.items()}
        if not valeurs["code"] :
            continue
        modeles = [modele.strip() for modele in valeurs.pop("modeles").split(",") if modele.strip()]
        if not modeles :
            logger.warning("onglet %s : code %s sans modèle concerné, ignoré", nom_onglet, valeurs["code"])
            continue
        erreurs.append(ErreurReferentiel(gamme=gamme, type_appareil=type_appareil, modeles=modeles, **valeurs))

    logger.debug("onglet %s : %d codes erreur (gamme %s, %s)", nom_onglet, len(erreurs), gamme, type_appareil)
    return erreurs, version


def lire_referentiel(chemin : Path, source : str) -> Referentiel :
    """lit tous les onglets du référentiel. source : identifiant du fichier (chemin relatif)"""
    erreurs, versions = [], set()
    for nom_onglet, feuille in pd.read_excel(chemin, sheet_name=None, header=None).items() :
        erreurs_onglet, version = _lire_onglet(feuille, nom_onglet)
        erreurs.extend(erreurs_onglet)
        if version :
            versions.add(version)

    if len(versions) > 1 :
        logger.warning("%s : versions différentes selon les onglets : %s", chemin.name, sorted(versions))
    version = sorted(versions)[-1] if versions else None
    logger.info("%s : %d codes erreur lus (version %s)", chemin.name, len(erreurs), version)
    return Referentiel(source=source, version=version, erreurs=erreurs)
