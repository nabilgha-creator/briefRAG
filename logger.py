import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# dossier des logs a la racine du projet (independant de l'endroit d'ou on lance le script)
DOSSIER_LOGS = Path(__file__).resolve().parent / "logs"
FICHIER_LOG = DOSSIER_LOGS / "briefrag.log"

FORMAT = "%(asctime)s - %(levelname)-8s - %(name)s - %(message)s"

# bibliotheques tres bavardes en INFO / DEBUG : on ne garde que leurs avertissements et erreurs
BIBLIOTHEQUES_BAVARDES = ("docling", "docling_core", "httpx", "httpcore", "huggingface_hub", "transformers", "urllib3", "PIL", "rapidocr")


def configurer_logs(niveau_console: int = logging.INFO) -> None:
    """configure les logs UNE fois, a appeler au demarrage du programme (point d'entree)

    - console : niveau_console et plus (INFO par defaut)
    - fichier logs/briefrag.log : tout a partir de DEBUG, 5 Mo max, 3 anciens fichiers gardes
    """
    racine = logging.getLogger()
    if racine.handlers:          # deja configure : on ne double pas les handlers
        return

    DOSSIER_LOGS.mkdir(exist_ok=True)
    formatter = logging.Formatter(FORMAT)

    console = logging.StreamHandler()
    console.setLevel(niveau_console)
    console.setFormatter(formatter)

    fichier = RotatingFileHandler(FICHIER_LOG, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    fichier.setLevel(logging.DEBUG)
    fichier.setFormatter(formatter)

    racine.setLevel(logging.DEBUG)
    racine.addHandler(console)
    racine.addHandler(fichier)

    for nom in BIBLIOTHEQUES_BAVARDES:
        logging.getLogger(nom).setLevel(logging.WARNING)
