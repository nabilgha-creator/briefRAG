import logging
from backend.chemin import DOCS

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
logging.FileHandler(filename=f"{DOCS}\log.py", encoding="utf-8")