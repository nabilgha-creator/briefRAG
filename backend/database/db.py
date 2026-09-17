import psycopg
import os 
from dotenv import load_dotenv

load_dotenv()
#connection a la base 

def get_connection():
    """ouvre une connection a la db"""
    try: 
        conn = psycopg.connect(host=os.getenv("DB_HOST"),
                                port = os.getenv("DB_PORT"),
                                dbname = os.getenv("DB_NAME"),
                                user = os.getenv("DB_USER"),
                                password = os.getenv("DB_PASSWORD"))
        return conn
    except Exception as e :
        return (f'defaut de connection a la base : {e}')

if __name__ == "__main__" :
    with get_connection() as conn :
        with conn.cursor() as cur :
            cur.execute("SELECT version(), current_database();")
            version , base = cur.fetchone()
            print("Connecte a :", base)
            print(version)