from sqlalchemy import create_engine, URL, text
from sqlalchemy.orm import sessionmaker
import os 
from dotenv import load_dotenv

load_dotenv()
#connection a la base 

DATABASE_URL = URL.create(drivername="postgresql+psycopg", #on crée la chaine url via URL.create 
                          username=os.getenv("DB_USER"),
                          password=os.getenv("DB_PASSWORD"),
                          host=os.getenv("DB_HOST"),
                          port=os.getenv("DB_PORT"),
                          database=os.getenv("DB_NAME"))

ECHO_SQL = os.getenv("DB_ECHO", "false").lower() == "true"     # DB_ECHO=true dans le .env pour afficher le SQL généré

engine = create_engine(DATABASE_URL, echo=ECHO_SQL) #on crée l'engine , le pool de connexion a la base
SessionLocal = sessionmaker(bind=engine) #mis en place d'une "fabrique" de session , permet d'utiliser une seule connexion plutôt qu'ouvrir une connexion par requete

def get_session():
    """renvoie une nouvelle session"""
    return SessionLocal() 


if __name__ == "__main__":
    with get_session() as session:
        version, base = session.execute(text("SELECT version(), current_database();")).one()
        print(base, "-", version)
    
    
    