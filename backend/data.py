
from pathlib import Path
from chemin import DOCS , ASSETS
from langchain_docling import DoclingLoader

from chunker import chunker

EXTENSIONS = {".pdf" , ".docx" , ".csv" , ".xlsx" , ".html"}

files = [c for c in DOCS.rglob("*") if c.is_file() and not c.name.startswith("~$") and c.suffix.lower() in EXTENSIONS]

def charger_doc (fichier : list[str] | str) :
    liste_doc = []
    counter = 0 
    for x in fichier : 
        try:
            doc = DoclingLoader(file_path= str(x) , chunker=chunker)
            file = doc.load()
            liste_doc.extend(file)
            counter += 1
            
        except Exception as e :
            print(f'exception {e} sur le fichier {x}')
    return liste_doc
         
if __name__ == "__main__" :
    document = charger_doc(files)
    
    with open(f"{ASSETS}/chunks.txt", "w", encoding="utf-8") as f:
        for x in document :
            f.write(f"{x.page_content} ================================================\n")
        