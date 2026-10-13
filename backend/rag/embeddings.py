"""calcul des vecteurs (embeddings) avec le modèle bge-m3, pour les chunks a l'ingestion et pour les questions a la recherche.

le modèle est chargé a la première utilisation (une seule fois) : importer ce module ne charge rien.
"""
import logging
import time
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from backend.config import DIMENSION_VECTEUR, MODELE_EMBEDDING

logger = logging.getLogger(__name__)

TAILLE_LOT = 16                 # textes encodés ensemble
TAILLE_ETAPE = 128              # textes entre deux messages de progression


@lru_cache
def _modele() -> SentenceTransformer :
    debut = time.perf_counter()
    modele = SentenceTransformer(MODELE_EMBEDDING)
    logger.info("modèle %s chargé en %.1f s (%s)", MODELE_EMBEDDING, time.perf_counter() - debut, modele.device)
    return modele


def vectoriser(textes : list[str]) -> list[list[float]] :
    """vecteurs normalisés des textes, dans le même ordre (normalisés : la distance cosinus est alors la bonne mesure)"""
    if not textes :
        return []
    modele, vecteurs, debut = _modele(), [], time.perf_counter()
    for depart in range(0, len(textes), TAILLE_ETAPE) :
        lot = modele.encode(textes[depart:depart + TAILLE_ETAPE], batch_size=TAILLE_LOT,
                            normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
        if lot.shape[1] != DIMENSION_VECTEUR :
            raise ValueError(f"le modèle produit des vecteurs de dimension {lot.shape[1]}, la base attend {DIMENSION_VECTEUR}")
        vecteurs.extend(lot.tolist())
        logger.info("vectorisation : %d / %d", len(vecteurs), len(textes))
    logger.info("%d textes vectorisés en %.0f s", len(textes), time.perf_counter() - debut)
    return vecteurs


def vectoriser_question(question : str) -> list[float] :
    """bge-m3 n'utilise pas d'instruction propre aux requêtes : la question est encodée comme les chunks"""
    return _modele().encode(question, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False).tolist()
