import json 
from db import get_connection
from chemin import ASSETS


with open(ASSETS/ "chunks.json" , "r", encoding="utf-8") as f :
    data = json.load(f)
    
    

