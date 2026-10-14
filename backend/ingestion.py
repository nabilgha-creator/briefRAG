"""ingestion incrémentale de la documentation : seuls les fichiers nouveaux ou modifiés (empreinte différente) sont retraités.
lancement depuis la racine du projet : python -m backend.ingestion [--tout]
"""
import argparse
import logging
import time
from collections import defaultdict

from sqlalchemy.orm import Session, sessionmaker

from backend.chargement.data import (FICHIER_REFERENTIEL, charger_documents, charger_referentiel, document_du_referentiel,
                                     empreinte_du_fichier, lister_fichiers, source_du_fichier)
from backend.database.crud import (ChunkACreer, ajouter_chunks, empreintes_des_documents, get_or_create_appareil, lister_documents,
                                   lister_modeles, recuperer_creer_erreur, remplacer_document, supprimer_document)
from backend.database.db import SessionLocal
from backend.rag.embeddings import vectoriser
from backend.chargement.schemas import DocumentCharge, Referentiel

logger = logging.getLogger(__name__)


def ingerer_referentiel(session : Session, referentiel : Referentiel) -> int :
    """crée ou met a jour les modeles et leurs erreurs ; renvoie le nombre d'erreurs"""
    nombre = 0
    for erreur in referentiel.erreurs :
        for modele in erreur.modeles :
            get_or_create_appareil(session, modele, erreur.type_appareil)
            recuperer_creer_erreur(session, modele, erreur.code, erreur.signification, erreur.conduite, erreur.intervention)
            nombre += 1
    return nombre


def _modeles_par_gamme(session : Session) -> dict[str, list[str]] :
    """{"WX": ["WX-300", ...]} : la gamme est le préfixe du nom du modèle"""
    par_gamme = defaultdict(list)
    for modele in lister_modeles(session) :
        par_gamme[modele.modele.split("-")[0]].append(modele.modele)
    return dict(par_gamme)


def _chunks_a_creer(document : DocumentCharge, vecteurs : list[list[float]], modeles_par_gamme : dict[str, list[str]]) -> list[ChunkACreer] :
    """gammes converties en modèles ; chaque code cité est lié a l'erreur de chacun de ces modèles"""
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


def ingerer_document(session : Session, document : DocumentCharge, vecteurs : list[list[float]],
                     modeles_par_gamme : dict[str, list[str]], empreinte : str | None = None) -> None :
    nouveau = remplacer_document(session, document.source, document.titre, document.version, categorie=document.type_document,
                                 empreinte=empreinte)
    ajouter_chunks(session, nouveau, _chunks_a_creer(document, vecteurs, modeles_par_gamme))


def supprimer_documents_absents(session : Session, sources_presentes : set[str]) -> int :
    """supprime les documents dont le fichier a disparu (sinon leurs chunks restent servis)"""
    absents = [document for document in lister_documents(session) if document.source not in sources_presentes]
    for document in absents :
        supprimer_document(session, document)
    return len(absents)


def a_traiter(empreintes_fichiers : dict[str, str], empreintes_en_base : dict[str, str | None], source_referentiel : str,
              tout : bool = False) -> tuple[bool, list[str]]:
    """(référentiel a retraiter, documents a retraiter). référentiel modifié = tout retraiter :
    les liens chunk -> modèle / erreur des documents inchangés en dépendent"""
    referentiel = tout or empreintes_en_base.get(source_referentiel) != empreintes_fichiers[source_referentiel]
    sources = [source for source, empreinte in empreintes_fichiers.items()
               if source != source_referentiel and (referentiel or empreintes_en_base.get(source) != empreinte)]
    return referentiel, sources


def ingerer(fabrique_session : sessionmaker = SessionLocal, tout : bool = False) -> None :
    debut = time.perf_counter()

    chemins = {source_du_fichier(fichier) : fichier for fichier in lister_fichiers()}
    source_referentiel = source_du_fichier(FICHIER_REFERENTIEL)
    empreintes = {source : empreinte_du_fichier(chemin) for source, chemin in chemins.items()}
    empreintes[source_referentiel] = empreinte_du_fichier(FICHIER_REFERENTIEL)
    with fabrique_session() as session :
        en_base = empreintes_des_documents(session)
    avec_referentiel, sources = a_traiter(empreintes, en_base, source_referentiel, tout)
    logger.info("%d document(s) a traiter, %d inchangé(s)%s", len(sources), len(chemins) - len(sources),
                " (référentiel modifié : tout est retraité)" if avec_referentiel else "")

    referentiel = charger_referentiel() if avec_referentiel else None
    documents = ([document_du_referentiel(referentiel)] if referentiel else []) + charger_documents([chemins[source] for source in sources])

    # vecteurs avant toute transaction : étape longue, sans verrou en base
    vecteurs = vectoriser([chunk.contenu for document in documents for chunk in document.chunks])
    vecteurs_par_document, depart = [], 0
    for document in documents :
        vecteurs_par_document.append(vecteurs[depart:depart + len(document.chunks)])
        depart += len(document.chunks)

    if referentiel :
        with fabrique_session.begin() as session :
            logger.info("référentiel enregistré : %d erreurs", ingerer_referentiel(session, referentiel))
    with fabrique_session() as session :
        modeles_par_gamme = _modeles_par_gamme(session)

    echecs = []
    for document, vecteurs_document in zip(documents, vecteurs_par_document, strict=True) :
        try :
            with fabrique_session.begin() as session :          # une transaction par document : un échec n'annule pas les autres
                ingerer_document(session, document, vecteurs_document, modeles_par_gamme, empreintes[document.source])
        except Exception :
            logger.exception("échec de l'ingestion de %s", document.source)
            echecs.append(document.source)

    # un fichier en échec garde sa version précédente (son empreinte en base n'a pas changé : réessayé la prochaine fois)
    with fabrique_session.begin() as session :
        supprimes = supprimer_documents_absents(session, set(chemins) | {source_referentiel})

    logger.info("ingestion terminée en %.0f s : %d document(s) retraité(s), %d chunks, %d échec(s), %d supprimé(s)",
                time.perf_counter() - debut, len(documents) - len(echecs),
                sum(len(document.chunks) for document in documents if document.source not in echecs), len(echecs), supprimes)
    if echecs :
        logger.warning("documents en échec : %s", ", ".join(echecs))


if __name__ == "__main__" :
    from logger import configurer_logs

    parametres = argparse.ArgumentParser(description="ingestion de la documentation")
    parametres.add_argument("--tout", action="store_true", help="retraiter tous les documents, même inchangés")
    configurer_logs()
    ingerer(tout=parametres.parse_args().tout)
