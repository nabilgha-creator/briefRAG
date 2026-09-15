from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOCS = RACINE / "assets" / "Documentation_Electrodomus"
if not DOCS.exists():
    raise FileNotFoundError