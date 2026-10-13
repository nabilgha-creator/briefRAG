from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
ASSETS = RACINE / "assets"
DOCS = ASSETS / "Documentation_Electrodomus"

if not ASSETS.exists() :
    raise FileNotFoundError(f"dossier assets introuvable : {ASSETS}")
if not DOCS.exists():
    raise FileNotFoundError(f"dossier de documentation introuvable : {DOCS}")
