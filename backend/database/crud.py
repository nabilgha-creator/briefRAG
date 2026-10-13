from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from backend.database.models import Document, Chunk, Modele , Erreur
from sqlalchemy import select, or_
import logging

logger = logging.getLogger(__name__)


## MODELES ##

def get_or_create_appareil (session : Session, modele : str , type_appareil : str | None = None) -> Modele :
    """recupère un modele , le crée s'il n'existe pas , si seul le type change il est mise a jour si la valeur n'est pas nulle """

    modele_demande = session.get(Modele, modele)

    if modele_demande is None:
        mod = Modele(modele=modele , type = type_appareil)
        session.add(mod)
        return mod
    if modele_demande.type != type_appareil:
        if type_appareil is not None:
            modele_demande.type = type_appareil

    return modele_demande


## ERREURS ##

def get_erreur(session : Session, modele : str, code_erreur : str) -> Erreur | None :
    """renvoie l'erreur du couple modele / code erreur, ou None si elle n'existe pas"""
    stmt = select(Erreur).where(Erreur.modele == modele, Erreur.code_erreur == code_erreur)
    return session.scalars(stmt).one_or_none()


def recuperer_creer_erreur(session : Session , modele : str , code_erreur : str , signification : str , conduite : str , intervention : str ) -> Erreur :
    """créer une erreur avec ses infos, les met a jour au besoin et la renvoi si elle existe déja, l'erreur est vérifié par un couple code erreur / modele ex : E41 pourrait avoir 2 signification selon les modèles d'appareils"""
    modele_actuel = get_or_create_appareil(session=session, modele=modele)
    erreur = get_erreur(session, modele_actuel.modele, code_erreur)
    if erreur is None :
        err = Erreur(modele = modele , code_erreur = code_erreur, signification = signification , conduite = conduite , intervention = intervention)
        session.add(err)
        return err

    erreur.intervention = intervention
    erreur.conduite = conduite
    erreur.signification = signification
    return erreur


## DOCUMENTS ##

def get_document(session : Session, titre : str, version : str | None = None) -> Document | None :
    """renvoie le document identifié par son titre et sa version, ou None (version None = document sans version)"""
    stmt = select(Document).where(Document.titre == titre, Document.version == version)
    return session.scalars(stmt).one_or_none()


def supprimer_document(session : Session, document : Document) -> None :
    """supprime un document, ses chunks et leurs liens modele / erreur partent avec (cascade)"""
    logger.info("suppression du document %s (version %s)", document.titre, document.version)
    session.delete(document)


def remplacer_document(session : Session, titre : str, version : str | None = None) -> Document :
    """crée un document vide ; s'il existe déjà (même titre et version) l'ancien et ses chunks sont supprimés avant.
    permet de relancer l'ingestion sans créer de doublons"""
    ancien = get_document(session, titre, version)
    if ancien is not None :
        supprimer_document(session, ancien)
        session.flush()

    document = Document(titre=titre, version=version)
    session.add(document)
    return document


## CHUNKS ##

@dataclass
class ChunkACreer :
    """données d'un chunk a insérer, indépendantes de langchain / docling"""
    contenu : str
    position : int | None = None
    vecteur : list[float] | None = None
    modeles : list[str] = field(default_factory=list)                 # ex : ["WX-300", "WX-350"]
    erreurs : list[tuple[str, str]] = field(default_factory=list)     # couples (modele, code_erreur), ex : [("WX-300", "E41")]


def ajouter_chunks(session : Session, document : Document, chunks : list[ChunkACreer]) -> list[Chunk] :
    """ajoute une liste de chunks a un document et les lie a leurs modeles et erreurs.
    les modeles inconnus sont créés, les erreurs inconnues sont ignorées (avec un warning) car il manque leurs infos"""
    erreurs_connues : dict[tuple[str, str], Erreur | None] = {}     # evite de refaire la meme requete pour chaque chunk
    nouveaux = []

    for donnees in chunks :
        # rattaché au document dès la création : sinon un flush automatique pourrait l'insérer sans id_document.
        # add explicite : depuis SQLAlchemy 2.0, rel_document=... ne fait pas entrer le chunk dans la session
        chunk = Chunk(position_chunk=donnees.position, contenu=donnees.contenu, vecteur=donnees.vecteur, rel_document=document)
        session.add(chunk)

        for modele in donnees.modeles :
            chunk.rel_chunk_modele.append(get_or_create_appareil(session, modele))

        for modele, code_erreur in donnees.erreurs :
            if (modele, code_erreur) not in erreurs_connues :
                erreurs_connues[(modele, code_erreur)] = get_erreur(session, modele, code_erreur)
            erreur = erreurs_connues[(modele, code_erreur)]
            if erreur is None :
                logger.warning("erreur %s inconnue pour le modele %s, lien ignoré (chunk %s de %s)", code_erreur, modele, donnees.position, document.titre)
            else :
                chunk.rel_chunk_erreur.append(erreur)

        nouveaux.append(chunk)

    logger.info("%d chunks ajoutés au document %s", len(nouveaux), document.titre)
    return nouveaux


## RECHERCHE ##

def rechercher_chunks(session : Session, vecteur : list[float], limite : int = 5, modele : str | None = None) -> list[tuple[Chunk, float]] :
    """renvoie les chunks les plus proches du vecteur de la question, du plus proche au plus loin, avec leur distance cosinus
    (0 = identique, 2 = opposé). si modele est donné, ne cherche que dans les chunks liés a ce modele
    et dans les chunks liés a aucun modele (documents généraux comme les CGV, valables pour tous les appareils)"""
    distance = Chunk.vecteur.cosine_distance(vecteur).label("distance")
    stmt = select(Chunk, distance).where(Chunk.vecteur.is_not(None))
    if modele is not None :
        stmt = stmt.where(or_(Chunk.rel_chunk_modele.any(Modele.modele == modele), ~Chunk.rel_chunk_modele.any()))
    stmt = stmt.order_by(distance).limit(limite)
    return list(session.execute(stmt).tuples())
