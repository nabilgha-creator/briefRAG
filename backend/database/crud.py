from dataclasses import dataclass, field
from sqlalchemy.orm import Session, selectinload
from backend.database.models import Document, Chunk, Modele , Erreur
from sqlalchemy import Select, func, or_, select
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


def lister_modeles(session : Session) -> list[Modele] :
    """tous les modeles, triés par nom"""
    return list(session.scalars(select(Modele).order_by(Modele.modele)))


## ERREURS ##

def get_erreur(session : Session, modele : str, code_erreur : str) -> Erreur | None :
    """renvoie l'erreur du couple modele / code erreur, ou None si elle n'existe pas"""
    stmt = select(Erreur).where(Erreur.modele == modele, Erreur.code_erreur == code_erreur)
    return session.scalars(stmt).one_or_none()


def lister_erreurs(session : Session, code_erreur : str, modeles : list[str]) -> list[Erreur] :
    """les erreurs de ce code pour ces modeles (un même code peut avoir un sens différent selon le modele)"""
    stmt = select(Erreur).where(Erreur.code_erreur == code_erreur, Erreur.modele.in_(modeles)).order_by(Erreur.modele)
    return list(session.scalars(stmt))


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

def get_document(session : Session, source : str) -> Document | None :
    """renvoie le document issu du fichier source (chemin relatif au dossier de documentation), ou None"""
    stmt = select(Document).where(Document.source == source)
    return session.scalars(stmt).one_or_none()


def lister_documents(session : Session) -> list[Document] :
    """tous les documents, triés par source"""
    return list(session.scalars(select(Document).order_by(Document.source)))


def get_document_par_categorie(session : Session, categorie : str) -> Document | None :
    """le premier document de cette catégorie (le référentiel des codes erreur est seul dans la sienne), ou None"""
    return session.scalars(select(Document).where(Document.categorie == categorie).order_by(Document.source)).first()


def supprimer_document(session : Session, document : Document) -> None :
    """supprime un document, ses chunks et leurs liens modele / erreur partent avec (cascade)"""
    logger.info("suppression du document %s (version %s)", document.source, document.version)
    session.delete(document)


def remplacer_document(session : Session, source : str, titre : str, version : str | None = None, *, categorie : str) -> Document :
    """crée un document vide ; si le fichier source a déjà été ingéré, l'ancien document et ses chunks sont supprimés avant
    (une nouvelle édition remplace donc la précédente). permet de relancer l'ingestion sans créer de doublons.
    categorie : Manuel, FAQ... (sert aux droits de lecture des rôles)"""
    ancien = get_document(session, source)
    if ancien is not None :
        supprimer_document(session, ancien)
        session.flush()

    document = Document(source=source, categorie=categorie, titre=titre, version=version)
    session.add(document)
    return document


## CHUNKS ##

@dataclass
class ChunkACreer :
    """données d'un chunk a insérer, indépendantes de langchain / docling"""
    contenu : str
    position : int | None = None
    vecteur : list[float] | None = None
    pages : list[int] = field(default_factory=list)                   # pages du document d'origine, vide si sans objet
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
        chunk = Chunk(position_chunk=donnees.position, contenu=donnees.contenu, vecteur=donnees.vecteur,
                      pages=donnees.pages or None, rel_document=document)
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


def get_chunk(session : Session, id_chunk : int) -> Chunk | None :
    """un chunk et son document, ou None (les identifiants changent quand un document est réingéré)"""
    return session.scalars(select(Chunk).where(Chunk.id_chunk == id_chunk).options(selectinload(Chunk.rel_document))).one_or_none()


## RECHERCHE ##

def rechercher_chunks(session : Session, vecteur : list[float], limite : int = 5, modeles : list[str] | None = None,
                      ids_erreurs : list[int] | None = None, categories : list[str] | None = None) -> list[tuple[Chunk, float]] :
    """renvoie les chunks les plus proches du vecteur de la question, du plus proche au plus loin, avec leur distance cosinus
    (0 = identique, 2 = opposé). le document de chaque chunk est chargé avec lui.
    - modeles : ne cherche que dans les chunks liés a l'un de ces modeles et dans les chunks liés a aucun modele
      (documents généraux comme les CGV, valables pour tous les appareils)
    - ids_erreurs : ne cherche que dans les chunks liés a l'une de ces erreurs
    - categories : ne cherche que dans les documents de ces catégories (droits de l'utilisateur) ;
      None = toutes, liste vide = aucune"""
    distance = Chunk.vecteur.cosine_distance(vecteur).label("distance")
    stmt = select(Chunk, distance).where(Chunk.vecteur.is_not(None)).options(selectinload(Chunk.rel_document))
    stmt = _filtrer(stmt, modeles, ids_erreurs, categories).order_by(distance).limit(limite)
    return list(session.execute(stmt).tuples())


def _filtrer(stmt : Select, modeles : list[str] | None, ids_erreurs : list[int] | None, categories : list[str] | None) -> Select :
    """filtres communs aux recherches par vecteurs et lexicale (modèles, erreurs, droits) : les deux recherches
    appliquent exactement les mêmes règles, et les droits ne sont écrits qu'une fois"""
    if modeles :
        stmt = stmt.where(or_(Chunk.rel_chunk_modele.any(Modele.modele.in_(modeles)), ~Chunk.rel_chunk_modele.any()))
    if ids_erreurs :
        stmt = stmt.where(Chunk.rel_chunk_erreur.any(Erreur.id_erreur.in_(ids_erreurs)))
    if categories is not None :
        stmt = stmt.where(Chunk.rel_document.has(Document.categorie.in_(categories)))
    return stmt


def ids_chunks_filtres(session : Session, modeles : list[str] | None = None, categories : list[str] | None = None) -> set[int] :
    """identifiants des chunks qui passent les filtres (mêmes règles que rechercher_chunks)"""
    return set(session.scalars(_filtrer(select(Chunk.id_chunk), modeles, None, categories)))


def chunks_avec_distance(session : Session, vecteur : list[float], ids_chunks : list[int]) -> list[tuple[Chunk, float]] :
    """ces chunks avec leur distance cosinus a la question (ceux trouvés par la recherche lexicale seule)"""
    if not ids_chunks :
        return []
    distance = Chunk.vecteur.cosine_distance(vecteur).label("distance")
    stmt = select(Chunk, distance).where(Chunk.id_chunk.in_(ids_chunks), Chunk.vecteur.is_not(None)).options(selectinload(Chunk.rel_document))
    return list(session.execute(stmt).tuples())


def textes_des_chunks(session : Session) -> list[tuple[int, str, str]] :
    """(id_chunk, contenu, source du document) de tous les chunks : de quoi construire l'index lexical"""
    stmt = select(Chunk.id_chunk, Chunk.contenu, Document.source).join(Chunk.rel_document)
    return list(session.execute(stmt).tuples())


def version_des_chunks(session : Session) -> tuple[int, int] :
    """(nombre de chunks, plus grand identifiant) : change a chaque ingestion (les chunks sont recréés)"""
    nombre, plus_grand = session.execute(select(func.count(Chunk.id_chunk), func.coalesce(func.max(Chunk.id_chunk), 0))).one()
    return nombre, plus_grand
