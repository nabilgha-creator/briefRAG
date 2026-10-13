"""application FastAPI : le point d'entrée HTTP du chatbot (front Vue.js).

lancement depuis la racine du projet :   uvicorn backend.api.app:app --reload
documentation interactive des routes :   http://localhost:8000/docs

réglage dans le .env : FRONT_ORIGINES = adresses autorisées a appeler l'API, séparées par des virgules
(défaut : http://localhost:5173, le serveur de développement de Vue / Vite)
"""
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import routes_auth, routes_conversations, routes_roles, routes_utilisateurs
from backend.auth.admin_initial import assurer_admin_initial
from backend.database.db import SessionLocal
from backend.rag.embeddings import vectoriser_question
from logger import configurer_logs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def cycle_de_vie(_ : FastAPI) -> AsyncIterator[None] :
    configurer_logs()
    with SessionLocal.begin() as session :
        assurer_admin_initial(session)       # compte admin d'amorçage du .env si aucun admin actif
    vectoriser_question("préchargement")     # charge bge-m3 au démarrage plutôt qu'a la 1re question (~10 s)
    logger.info("API prête")
    yield


app = FastAPI(title="BriefRAG — assistant SAV Electrodomus", version="1.0", lifespan=cycle_de_vie)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origine.strip() for origine in os.getenv("FRONT_ORIGINES", "http://localhost:5173").split(",") if origine.strip()],
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(routes_auth.routeur)
app.include_router(routes_utilisateurs.routeur)
app.include_router(routes_roles.routeur)
app.include_router(routes_conversations.routeur)


@app.get("/sante", tags=["supervision"])
def sante() -> dict[str, str] :
    return {"statut": "ok"}
