
from pathlib import Path
from chemin import DOCS , ASSETS
from langchain_docling import DoclingLoader
import json

from chunker import chunker



EXTENSIONS = {".pdf" , ".docx" , ".csv" , ".xlsx" , ".html"}

files = [c for c in DOCS.rglob("*") if c.is_file() and not c.name.startswith("~$") and c.suffix.lower() in EXTENSIONS]

def charger_doc (fichier : list[str] | str) :
    liste_doc = []

    for x in fichier : 
        try:
            loader = DoclingLoader(file_path= str(x) , chunker=chunker)
            doc = loader.load()
            liste_doc.extend(doc)
            
        except Exception as e :
            print(f'exception {e} sur le fichier {x}')
    return liste_doc
         
if __name__ == "__main__" :
    document = charger_doc(files)
    doc_list= [{"contenu": x.page_content, "metadata": x.metadata} for x in document]
    print(json.dumps(document[0].metadata , indent= 4 , default = str))
    with open(f"{ASSETS}/chunks.json", "w", encoding="utf-8") as f:
        json.dump(doc_list, f , indent= 4 , ensure_ascii=False, default=str)
        