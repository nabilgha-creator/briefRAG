"""réglages partagés par tout le backend : chemins, modèle d'embedding, catégories de documents.
(les réglages propres a une partie restent dans son module : base dans database/db.py, LLM dans rag/llm.py)"""
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
ASSETS = RACINE / "assets"
DOCS = ASSETS / "Documentation_Electrodomus"

if not ASSETS.exists() :
    raise FileNotFoundError(f"dossier assets introuvable : {ASSETS}")
if not DOCS.exists():
    raise FileNotFoundError(f"dossier de documentation introuvable : {DOCS}")

# le même modèle sert au découpage (comptage des tokens), aux vecteurs des chunks et a ceux des questions
MODELE_EMBEDDING = "BAAI/bge-m3"
DIMENSION_VECTEUR = 1024        # doit correspondre a Vector(1024) dans database/models.py

# catégories de documents : affichées dans le contexte des chunks ("[Manuel] ...") et utilisées pour les droits
# de lecture des rôles. dossier de rangement de la documentation -> catégorie
CATEGORIES_PAR_DOSSIER = {
    "Manuels": "Manuel",
    "Procedures_SAV": "Procédure SAV",
    "Bulletins_techniques": "Bulletin technique",
    "Garanties": "Garantie",
    "FAQ": "FAQ",
}
CATEGORIE_REFERENTIEL = "Référentiel codes erreur"      # référentiel excel : ses chunks ET les fiches erreur exactes
CATEGORIE_PAR_DEFAUT = "Document"                        # fichier rangé hors des dossiers connus
CATEGORIES = [*CATEGORIES_PAR_DOSSIER.values(), CATEGORIE_REFERENTIEL, CATEGORIE_PAR_DEFAUT]
