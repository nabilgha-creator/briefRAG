from transformers import AutoTokenizer
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer 
from docling.chunking import HybridChunker 
from docling_core.transforms.chunker.line_chunker import LineBasedTokenChunker
from dotenv import load_dotenv

load_dotenv()

tokenizer = HuggingFaceTokenizer(
    tokenizer=AutoTokenizer.from_pretrained("BAAI/bge-m3"),
    max_tokens= 512
)

ligne_tokenizer = HuggingFaceTokenizer(
    tokenizer=AutoTokenizer.from_pretrained("BAAI/bge-m3"),
    max_tokens= 2000
)

chunker = HybridChunker(tokenizer=tokenizer, merge_peers=True)

chunker_ligne = LineBasedTokenChunker(tokenizer=ligne_tokenizer , omit_prefix_on_overflow=False )

