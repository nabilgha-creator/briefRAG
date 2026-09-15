
from pathlib import Path
from chemin import DOCS
from langchain_docling import DoclingLoader

from chunker import chunker

EXTENSIONS = {".pdf" , ".docx" , ".csv" , ".xlsx" , ".html"}

files = [c for c in DOCS.rglob("*") if c.is_file() and not c.name.startswith("~$") and c.suffix.lower() in EXTENSIONS]

def charger_doc (fichier : list[str] | str) :
    liste_doc = []

    for x in fichier :
        try:
            doc = DoclingLoader(file_path= str(x) , chunker=chunker)
            file = doc.load()
            liste_doc.extend(file)
            
        except Exception as e :
            print(f'exception {e} sur le fichier {x}')
    print(len(files))
    print(len(liste_doc))
    return liste_doc
         
if __name__ == "main" :
    document = charger_doc(files)