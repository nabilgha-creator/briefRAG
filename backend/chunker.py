from transformers import AutoTokenizer
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling.chunking import HybridChunker  
from dotenv import load_dotenv

load_dotenv()

tokenizer = HuggingFaceTokenizer(
    tokenizer=AutoTokenizer.from_pretrained("BAAI/bge-m3"),
    max_tokens=512 
)

chunker = HybridChunker(tokenizer=tokenizer, merge_peers=True)



