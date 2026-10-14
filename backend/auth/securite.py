"""mots de passe (scrypt + sel, paramètres gardés dans l'empreinte) et jetons (seule leur empreinte sha256
est stockée), avec la bibliothèque standard"""
import base64
import hashlib
import hmac
import secrets

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
TAILLE_SEL = 16
TAILLE_EMPREINTE = 32
LONGUEUR_MIN_MOT_DE_PASSE = 8


def _b64(octets : bytes) -> str :
    return base64.b64encode(octets).decode("ascii")


def hacher_mot_de_passe(mot_de_passe : str) -> str :
    if len(mot_de_passe) < LONGUEUR_MIN_MOT_DE_PASSE :
        raise ValueError(f"le mot de passe doit faire au moins {LONGUEUR_MIN_MOT_DE_PASSE} caractères")
    sel = secrets.token_bytes(TAILLE_SEL)
    empreinte = hashlib.scrypt(mot_de_passe.encode("utf-8"), salt=sel, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=TAILLE_EMPREINTE)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(sel)}${_b64(empreinte)}"


def empreinte_valide(empreinte : str) -> bool :
    """vrai si le texte a la forme d'une empreinte produite par hacher_mot_de_passe"""
    morceaux = empreinte.split("$")
    if len(morceaux) != 6 or morceaux[0] != "scrypt" :
        return False
    try :
        int(morceaux[1]), int(morceaux[2]), int(morceaux[3])
        base64.b64decode(morceaux[4], validate=True), base64.b64decode(morceaux[5], validate=True)
    except ValueError :
        return False
    return True


def verifier_mot_de_passe(mot_de_passe : str, stocke : str) -> bool :
    try :
        algo, n, r, p, sel, empreinte = stocke.split("$")
        if algo != "scrypt" :
            return False
        attendue = base64.b64decode(empreinte)
        calculee = hashlib.scrypt(mot_de_passe.encode("utf-8"), salt=base64.b64decode(sel), n=int(n), r=int(r), p=int(p), dklen=len(attendue))
    except ValueError :
        return False
    return hmac.compare_digest(calculee, attendue)      # comparaison en temps constant


def generer_jeton() -> str :
    return secrets.token_urlsafe(32)


def empreinte_jeton(jeton : str) -> str :
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()
