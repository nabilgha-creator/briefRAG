"""droits de lecture de la documentation : quelles catégories de documents un compte peut consulter."""
from backend.database.models import Utilisateur


def categories_autorisees(utilisateur : Utilisateur) -> list[str] | None :
    """None = tout (administrateur) ; sinon l'union des catégories de ses rôles (liste vide = aucun document)"""
    if utilisateur.role == "admin" :
        return None
    return sorted({categorie for role in utilisateur.rel_role for categorie in role.categories})


def peut_lire(utilisateur : Utilisateur, categorie : str) -> bool :
    """vrai si le compte peut consulter les documents de cette catégorie"""
    autorisees = categories_autorisees(utilisateur)
    return autorisees is None or categorie in autorisees
