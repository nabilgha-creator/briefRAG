from db import get_connection


with get_connection as conn :
    with conn.cursor() as cur :
        cur.execute(
            "INSERT INTO document (titre) VALUES (%s)", 
                    ("doctest")", 
        )