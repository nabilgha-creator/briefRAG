from sqlalchemy import create_engine, URL, text
import os 
from dotenv import load_dotenv

load_dotenv()
#connection a la base 

def get_connection():
    """ouvre une connection a la db"""
    try: 
        DATABASE_URL =URL.create("postgresql+psycopg",username=os.getenv("DB_USER"),
                                 password=os.getenv("DB_PASSWORD"), host=os.getenv("DB_HOST") , 
                                 port= os.getenv("DB_PORT"))
        engine = create_engine(DATABASE_URL, echo=True)
        conn = engine.connect()
        return conn
    except Exception as e :
        return (f'defaut de connection a la base : {e}') 


if __name__ == "__main__" :
    conn = get_connection()
    base = conn.execute(text("SELECT version(), current_database();"))
    base = base.fetchone()
    conn.close()
    
    
    