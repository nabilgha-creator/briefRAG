
from pathlib import Path
from chemin import DOCS

files = list(DOCS.rglob(pattern="*"))


for x in files :
    if x.is_file():
        match x : 
            case x.suffix('.docx') : 
                 