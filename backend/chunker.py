"""configuration du découpage : tokenizer du modèle d'embedding et chunkers Docling.

les objets sont créés a la premiere utilisation (et une seule fois) plutôt qu'a l'import :
importer ce module ne télécharge / ne charge rien.
"""
from functools import lru_cache

from transformers import AutoTokenizer, PreTrainedTokenizerBase
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling.chunking import HybridChunker
from docling_core.transforms.chunker.line_chunker import LineBasedTokenChunker
from dotenv import load_dotenv

load_dotenv()   # HF_TOKEN

MODELE_EMBEDDING = "BAAI/bge-m3"
MAX_TOKENS_CHUNK = 512
TOKENS_RESERVES_CONTEXTE = 64      # place laissée au préfixe "[type] titre du document" ajouté après le découpage
MAX_TOKENS_LIGNE = 300


@lru_cache
def _tokenizer_hf() -> PreTrainedTokenizerBase :
    return AutoTokenizer.from_pretrained(MODELE_EMBEDDING)


def compter_tokens(texte : str) -> int :
    """nombre de tokens du texte pour le modèle d'embedding"""
    return len(_tokenizer_hf().encode(texte, add_special_tokens=False))


@lru_cache
def creer_chunker() -> HybridChunker :
    """chunker des documents structurés (pdf, docx) : suit les sections, fusionne les petits morceaux voisins
    de la même section, et répète l'en-tête des tableaux découpés sur plusieurs chunks"""
    tokenizer = HuggingFaceTokenizer(tokenizer=_tokenizer_hf(), max_tokens=MAX_TOKENS_CHUNK - TOKENS_RESERVES_CONTEXTE)
    return HybridChunker(tokenizer=tokenizer, merge_peers=True, repeat_table_header=True)


@lru_cache
def creer_chunker_ligne() -> LineBasedTokenChunker :
    """chunker ligne par ligne (tableaux type excel)"""
    tokenizer = HuggingFaceTokenizer(tokenizer=_tokenizer_hf(), max_tokens=MAX_TOKENS_LIGNE)
    return LineBasedTokenChunker(tokenizer=tokenizer, omit_prefix_on_overflow=False)
