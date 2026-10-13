"""ingestion de la documentation en base.

étapes :
1. lecture et découpage du référentiel et des documents (data.py), sans toucher a la base
2. calcul des vecteurs de tous les chunks, avant d'ouvrir une transaction (c'est l'étape longue)
3. référentiel -> tables modele et erreur, en une transaction (les liens chunk / erreur en dépendent)
4. chaque document -> document, chunks et liens modele / erreur, une transaction par document :
   un document en échec n'empêche pas les autres et ne laisse rien a moitié écrit
5. suppression des documents dont le fichier n'existe plus

relançable : un document déjà ingéré est remplacé (cf. remplacer_document).
lancement depuis la racine du projet : python -m backend.ingestion
"""
import logging
import time
from collections import defaultdict

from sqlalchemy.orm import Session, sessionmaker

from backend.chargement.data import charger_documents, charger_referentiel, document_du_referentiel, lister_fichiers, source_du_fichier
from backend.database.crud import (ChunkACreer, ajouter_chunks, get_or_create_appareil, lister_documents, lister_modeles,
                                   recuperer_creer_erreur, remplacer_document, supprimer_document)
from backend.database.db import SessionLocal
from backend.rag.embeddings import vectoriser
from backend.chargement.schemas import DocumentCharge, Referentiel

logger = logging.getLogger(__name__)


def ingerer_referentiel(session : Session, referentiel : Referentiel) -> int :
    """crée ou met a jour les modeles (avec leur type d'appareil) et leurs erreurs. renvoie le nombre d'erreurs"""
    nombre = 0
    for erreur in referentiel.erreurs :
        for modele in erreur.modeles :
            get_or_create_appareil(session, modele, erreur.type_appareil)
            recuperer_creer_erreur(session, modele, erreur.code, erreur.signification, erreur.conduite, erreur.intervention)
            nombre += 1
    return nombre


def _modeles_par_gamme(session : Session) -> dict[str, list[str]] :
    """{"WX": ["WX-300", ...], ...} d'après les modeles en base (la gamme est le préfixe du nom)"""
    par_gamme = defaultdict(list)
    for modele in lister_modeles(session) :
        par_gamme[modele.modele.split("-")[0]].append(modele.modele)
    return dict(par_gamme)


def _chunks_a_creer(document : DocumentCharge, vecteurs : list[list[float]], modeles_par_gamme : dict[str, list[str]]) -> list[ChunkACreer] :
    """traduit les chunks chargés pour le CRUD : les gammes deviennent leurs modèles,
    et chaque code erreur cité est lié a l'erreur de chacun de ces modèles"""
    chunks = []
    for chunk, vecteur in zip(document.chunks, vecteurs, strict=True) :
        modeles = set(chunk.modeles)
        for gamme in chunk.gammes :
            if gamme not in modeles_par_gamme :
                logger.warning("%s : gamme %s inconnue en base (chunk %d)", document.source, gamme, chunk.position)
            modeles.update(modeles_par_gamme.get(gamme, []))
        modeles = sorted(modeles)
        chunks.append(ChunkACreer(contenu=chunk.contenu, position=chunk.position, vecteur=vecteur, pages=chunk.pages,
                                  modeles=modeles, erreurs=[(modele, code) for modele in modeles for code in chunk.codes_erreur]))
    return chunks


def ingerer_document(session : Session, document : DocumentCharge, vecteurs : list[list[float]], modeles_par_gamme : dict[str, list[str]]) -> None :
    nouveau = remplacer_document(session, document.source, document.titre, document.version, categorie=document.type_document)
    ajouter_chunks(session, nouveau, _chunks_a_creer(document, vecteurs, modeles_par_gamme))


def supprimer_documents_absents(session : Session, sources_presentes : set[str]) -> int :
    """supprime les documents dont le fichier a disparu : sinon leurs chunks continueraient d'être servis"""
    absents = [document for document in lister_documents(session) if document.source not in sources_presentes]
    for document in absents :
        supprimer_document(session, document)
    return len(absents)


def ingerer(fabrique_session : sessionmaker = SessionLocal) -> None :
    debut = time.perf_counter()

    referentiel = charger_referentiel()
    fichiers = lister_fichiers()
    documents = [document_du_referentiel(referentiel)] + charger_documents(fichiers)

    vecteurs = vectoriser([chunk.contenu for document in documents for chunk in document.chunks])
    vecteurs_par_document, depart = [], 0
    for document in documents :
        vecteurs_par_document.append(vecteurs[depart:depart + len(document.chunks)])
        depart += len(document.chunks)

    with fabrique_session.begin() as session :
        nombre_erreurs = ingerer_referentiel(session, referentiel)
    logger.info("référentiel enregistré : %d erreurs", nombre_erreurs)

    with fabrique_session() as session :
        modeles_par_gamme = _modeles_par_gamme(session)

    echecs = []
    for document, vecteurs_document in zip(documents, vecteurs_par_document, strict=True) :
        try :
            with fabrique_session.begin() as session :
                ingerer_document(session, document, vecteurs_document, modeles_par_gamme)
        except Exception :
            logger.exception("échec de l'ingestion de %s", document.source)
            echecs.append(document.source)

    # sources des fichiers présents sur le disque, y compris ceux en échec : leur version précédente est gardée
    sources_presentes = {source_du_fichier(fichier) for fichier in fichiers} | {referentiel.source}
    with fabrique_session.begin() as session :
        supprimes = supprimer_documents_absents(session, sources_presentes)

    logger.info("ingestion terminée en %.0f s : %d documents, %d chunks, %d échec(s), %d document(s) supprimé(s)",
                time.perf_counter() - debut, len(documents) - len(echecs),
                sum(len(document.chunks) for document in documents if document.source not in echecs), len(echecs), supprimes)
    if echecs :
        logger.warning("documents en échec : %s", ", ".join(echecs))


if __name__ == "__main__" :
    from logger import configurer_logs

    configurer_logs()
    ingerer()
