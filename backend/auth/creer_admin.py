"""création d'un compte administrateur (le premier compte, ou en secours), sans passer par l'API.
lancement depuis la racine du projet : python -m backend.auth.creer_admin
le mot de passe est saisi sans s'afficher.
"""
from getpass import getpass

from backend.database.crud_utilisateurs import creer_utilisateur
from backend.database.db import SessionLocal


def main() -> None :
    identifiant = input("Identifiant : ").strip()
    nom = input("Nom affiché : ").strip()
    mot_de_passe = getpass("Mot de passe : ")
    if mot_de_passe != getpass("Confirmation : ") :
        print("les deux mots de passe sont différents")
        return
    with SessionLocal.begin() as session :
        try :
            creer_utilisateur(session, identifiant, nom, mot_de_passe, role="admin")
        except ValueError as erreur :
            print(f"impossible : {erreur}")
            return
    print(f"administrateur {identifiant} créé")


if __name__ == "__main__" :
    from logger import configurer_logs

    configurer_logs()
    main()
