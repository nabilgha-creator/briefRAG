"""documents du lecteur : fichier, aperçu HTML, passage cité. droits des rôles appliqués ;
seules les sources enregistrées en base sont servies"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.api.dependances import SessionBD, UtilisateurConnecte
from backend.api.schemas import Apercu, Passage
from backend.auth.droits import peut_lire
from backend.chargement.apercu import FORMATS_APERCU, DocumentIntrouvable, apercu_html, chemin_du_document
from backend.database.crud import get_chunk, get_document
from backend.database.models import Document, Utilisateur

logger = logging.getLogger(__name__)

routeur = APIRouter(prefix="/documents", tags=["documents"])

TYPES_MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".html": "text/html",
}


def _verifier_droit(utilisateur : Utilisateur, document : Document) -> None :
    if not peut_lire(utilisateur, document.categorie) :
        logger.warning("%s : accès refusé au document %s (%s)", utilisateur.identifiant, document.source, document.categorie)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "vous n'avez pas accès à ce document")


def _document_lisible(session : Session, source : str, utilisateur : Utilisateur) -> tuple[Document, Path] :
    """le document et son fichier, si la source est en base, lisible par ce compte, et présente sur le disque"""
    document = get_document(session, source)
    if document is None :
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document introuvable")
    _verifier_droit(utilisateur, document)
    try :
        chemin = chemin_du_document(source)
    except DocumentIntrouvable as erreur :
        logger.error("document %s en base mais fichier absent du disque : réingérer la documentation", source)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "fichier introuvable sur le serveur") from erreur
    return document, chemin


@routeur.get("/fichier")
def fichier(source : str, utilisateur : UtilisateurConnecte, session : SessionBD, telechargement : bool = False) -> FileResponse :
    """le fichier d'origine : affiché par le lecteur (pdf), ou téléchargé (telechargement=true)"""
    _, chemin = _document_lisible(session, source, utilisateur)
    logger.info("%s ouvre %s%s", utilisateur.identifiant, source, " (téléchargement)" if telechargement else "")
    return FileResponse(chemin, media_type=TYPES_MIME.get(chemin.suffix.lower()), filename=chemin.name,
                        content_disposition_type="attachment" if telechargement else "inline")


@routeur.get("/apercu", response_model=Apercu)
def apercu(source : str, utilisateur : UtilisateurConnecte, session : SessionBD) -> Apercu :
    """aperçu HTML d'un document docx, xlsx ou html"""
    document, chemin = _document_lisible(session, source, utilisateur)
    if chemin.suffix.lower() not in FORMATS_APERCU :
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"pas d'aperçu pour un fichier {chemin.suffix} : utiliser /documents/fichier")
    logger.info("%s ouvre l'aperçu de %s", utilisateur.identifiant, source)
    return Apercu(source=document.source, titre=document.titre, categorie=document.categorie, html=apercu_html(chemin))


@routeur.get("/passages/{id_chunk}", response_model=Passage)
def passage(id_chunk : int, utilisateur : UtilisateurConnecte, session : SessionBD) -> Passage :
    """le texte complet d'un extrait cité (sa 1re ligne, « [catégorie] titre du document », est retirée)"""
    chunk = get_chunk(session, id_chunk)
    if chunk is None :
        raise HTTPException(status.HTTP_404_NOT_FOUND, "passage introuvable (le document a peut-être été réingéré)")
    _verifier_droit(utilisateur, chunk.rel_document)
    return Passage(id_chunk=chunk.id_chunk, source=chunk.rel_document.source, pages=chunk.pages or [],
                   texte=chunk.contenu.split("\n", 1)[-1])
