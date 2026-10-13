"""réglages partagés par tout le backend : chemins et modèle d'embedding.
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
