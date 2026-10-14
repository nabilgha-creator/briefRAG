"""coordonnées du SAV client, affichées par le bouton « Contacter le SAV » des réponses"""
from fastapi import APIRouter

from backend.api.dependances import UtilisateurConnecte
from backend.api.schemas import ContactSav
from backend.config import CONTACT_SAV

routeur = APIRouter(prefix="/sav", tags=["SAV"])


@routeur.get("", response_model=ContactSav)
def contact(_ : UtilisateurConnecte) -> ContactSav :
    return ContactSav(**CONTACT_SAV)
