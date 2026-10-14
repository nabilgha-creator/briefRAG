"""configuration du découpage : tokenizer du modèle d'embedding et chunker Docling.

les objets sont créés a la premiere utilisation (et une seule fois) plutôt qu'a l'import :
importer ce module ne télécharge / ne charge rien.
"""
from functools import lru_cache
from typing import Any

from transformers import AutoTokenizer, PreTrainedTokenizerBase
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.transforms.chunker.hierarchical_chunker import ChunkingDocSerializer, ChunkingSerializerProvider, TripletTableSerializer
from docling_core.transforms.serializer.base import BaseDocSerializer, BaseTableSerializer, SerializationResult
from docling_core.transforms.serializer.common import create_ser_result
from docling_core.types.doc import DoclingDocument, TableItem
from docling.chunking import HybridChunker
from dotenv import load_dotenv

from backend.config import MODELE_EMBEDDING

load_dotenv()   # HF_TOKEN

MAX_TOKENS_CHUNK = 512
TOKENS_RESERVES_CONTEXTE = 64      # place laissée au préfixe "[type] titre du document" ajouté après le découpage


@lru_cache
def _tokenizer_hf() -> PreTrainedTokenizerBase :
    return AutoTokenizer.from_pretrained(MODELE_EMBEDDING)


def compter_tokens(texte : str) -> int :
    """nombre de tokens du texte pour le modèle d'embedding"""
    return len(_tokenizer_hf().encode(texte, add_special_tokens=False))


## SÉRIALISATION DES TABLEAUX ##

class SerialiseurTableauParLigne(TripletTableSerializer) :
    """même format que Docling ("E01, Signification = Porte mal verrouillée") mais une ligne de texte par ligne
    du tableau. Docling écrit tout le tableau sur une seule ligne : un grand tableau est alors coupé au milieu
    d'une ligne. ici le chunker découpe ligne par ligne, et chaque ligne reste lisible seule (elle porte ses colonnes)"""

    def serialize(self, *, item : TableItem, doc_serializer : BaseDocSerializer, doc : DoclingDocument, **kwargs : Any) -> SerializationResult :
        tableau = item.export_to_dataframe(doc=doc)
        if item.self_ref in doc_serializer.get_excluded_refs(**kwargs) or tableau.shape[0] == 0 or tableau.shape[1] < 2 :
            return super().serialize(item=item, doc_serializer=doc_serializer, doc=doc, **kwargs)

        colonnes = [str(colonne).strip() for colonne in tableau.columns]
        lignes = []
        for valeurs in tableau.itertuples(index=False, name=None) :
            valeurs = [str(valeur).strip().rstrip(".") for valeur in valeurs]
            cellules = [f"{valeurs[0]}, {colonne} = {valeur}" for colonne, valeur in zip(colonnes[1:], valeurs[1:]) if valeur]
            if cellules :
                lignes.append(". ".join(cellules) + ".")
        if not lignes :
            return super().serialize(item=item, doc_serializer=doc_serializer, doc=doc, **kwargs)
        return create_ser_result(text="\n".join(lignes), span_source=item)

    def get_header_and_body_lines(self, *, table_text : str, **kwargs : Any) -> tuple[list[str], list[str]] :
        """lignes utilisées quand le chunker coupe un grand tableau : il les recolle telles quelles,
        elles gardent donc leur saut de ligne (pas d'en-tête : chaque ligne porte déjà le nom de ses colonnes)"""
        return [], [f"{ligne}\n" for ligne in table_text.splitlines() if ligne.strip()]


class SerialiseurDocument(ChunkingDocSerializer) :
    table_serializer : BaseTableSerializer = SerialiseurTableauParLigne()


class FournisseurSerialiseur(ChunkingSerializerProvider) :
    def get_serializer(self, doc : DoclingDocument) -> BaseDocSerializer :
        return SerialiseurDocument(doc=doc)


## CHUNKER ##

@lru_cache
def creer_chunker() -> HybridChunker :
    """chunker des documents structurés (pdf, docx) : suit les sections, fusionne les petits morceaux voisins
    de la même section, et découpe les grands tableaux entre deux lignes.
    (le référentiel excel n'en a pas besoin : data.py en fait un chunk par code erreur)"""
    tokenizer = HuggingFaceTokenizer(tokenizer=_tokenizer_hf(), max_tokens=MAX_TOKENS_CHUNK - TOKENS_RESERVES_CONTEXTE)
    return HybridChunker(tokenizer=tokenizer, merge_peers=True, repeat_table_header=True, serializer_provider=FournisseurSerialiseur())
