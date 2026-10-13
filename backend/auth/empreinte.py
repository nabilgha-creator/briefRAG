"""calcule l'empreinte d'un mot de passe pour le compte administrateur d'amorçage du .env.
lancement depuis la racine du projet : python -m backend.auth.empreinte
le mot de passe est saisi sans s'afficher ; seule son empreinte est affichée, a copier dans le .env.
"""
from getpass import getpass

from backend.auth.securite import LONGUEUR_MIN_MOT_DE_PASSE, hacher_mot_de_passe


def main() -> None :
    mot_de_passe = getpass(f"Mot de passe de l'administrateur ({LONGUEUR_MIN_MOT_DE_PASSE} caractères minimum) : ")
    if mot_de_passe != getpass("Confirmation : ") :
        print("les deux mots de passe sont différents")
        return
    try :
        empreinte = hacher_mot_de_passe(mot_de_passe)
    except ValueError as erreur :
        print(erreur)
        return
    print("\nAjoutez ces lignes au fichier .env (les guillemets simples sont nécessaires), puis redémarrez l'API :\n")
    print("ADMIN_IDENTIFIANT=admin")
    print(f"ADMIN_EMPREINTE='{empreinte}'")


if __name__ == "__main__" :
    main()
