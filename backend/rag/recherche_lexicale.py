"""recherche lexicale BM25, en concurrence avec les vecteurs (termes exacts : pièces, bulletins, mots rares).
une référence citée compte double ; index en mémoire, reconstruit quand les chunks changent"""
import logging
import math
import re
import threading
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass

import snowballstemmer
from sqlalchemy.orm import Session

from backend.database.crud import ids_chunks_filtres, textes_des_chunks, version_des_chunks

logger = logging.getLogger(__name__)

K1 = 1.5                    # saturation de la fréquence d'un terme
B = 0.75                    # normalisation par la longueur du chunk (0 = aucune, 1 = complète)
POIDS_REFERENCE = 2.0       # une référence (code erreur, pièce, bulletin, procédure) compte double
PART_DISCRIMINANTE = 0.05   # terme discriminant : présent dans au plus 5 % des chunks ("eau" : 34 %)

# motifs reconnus, sur le texte en minuscules sans accents. les références pinpointent un contenu précis ;
# les modèles servent déjà de filtre (recherche.py) : ils comptent comme des mots ordinaires
MOTIFS_REFERENCE = [
    (re.compile(r"\bbt-?(\d{4})-?(\d{3})\b"), "bt-{}-{}"),            # bulletin technique : BT-2026-011
    (re.compile(r"\bproc-?([a-z]{2})-?(\d{2})\b"), "proc-{}-{}"),     # procédure SAV : PROC-WX-03
    (re.compile(r"\b(\d{2})-(\d{4})\b"), "{}-{}"),                    # référence de pièce : 44-3311
    (re.compile(r"\be\s?(\d{2})\b"), "e{}"),                          # code erreur : E23, e 23
]
MOTIF_MODELE = (re.compile(r"\b(wx|lv|fr)[\s-]?(\d{3})\b"), "{}-{}")  # WX-500, wx500, WX 500
RE_MOT = re.compile(r"[^\W_]+")                                        # lettres (accents compris) et chiffres

# mots sans valeur pour distinguer les chunks (articles, pronoms, mots des questions)
MOTS_VIDES = set("""
a au aux avec ce ces cet cette comment dans de des du elle en est et etre faire fait faut il ils je la le les leur
lui ma mais me mes mon ne nous on ou par pas peut peux plus pour quand que quel quelle quelles quels qui quoi sa se
ses si son sont sur ta te tes ton tu un une vos votre vous y doit dois avoir ai as avez ont
""".split())


@dataclass
class Termes :
    """les termes d'un texte : mots, modèles et références (une référence est aussi un terme)"""
    tous : list[str]
    references : set[str]
    modeles : set[str]


def _sans_accents(texte : str) -> str :
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(caractere for caractere in decompose if not unicodedata.combining(caractere))


def decouper(texte : str) -> Termes :
    """termes d'un texte (question ou chunk) ; racines Snowball : « évacue », « évacuation » -> évacu"""
    texte = texte.lower().replace("_", " ").replace("’", "'")
    tous, references, modeles = [], set(), set()
    for motif, forme in [*MOTIFS_REFERENCE, MOTIF_MODELE] :
        for trouve in motif.finditer(texte) :
            terme = forme.format(*trouve.groups())
            tous.append(terme)
            (modeles if (motif, forme) == MOTIF_MODELE else references).add(terme)
        texte = motif.sub(" ", texte)       # les morceaux d'une référence ("44", "3311") ne comptent pas en plus
    racineur = snowballstemmer.stemmer("french")        # une instance par appel : le racineur n'est pas sûr entre threads
    mots = [mot for mot in RE_MOT.findall(texte) if len(mot) > 1 and _sans_accents(mot) not in MOTS_VIDES]
    tous += [_sans_accents(racine) for racine in racineur.stemWords(mots)]
    return Termes(tous, references, modeles)


@dataclass
class ResultatLexical :
    id_chunk : int
    score : float
    references : list[str]          # références de la question trouvées dans ce chunk


class IndexLexical :
    """index BM25 : pour chaque chunk, le nombre d'occurrences de chaque terme"""

    def __init__(self, textes : list[tuple[int, str]], version : tuple = (), part_discriminante : float = PART_DISCRIMINANTE) -> None :
        self.version = version
        self.part_discriminante = part_discriminante
        self.frequences = {id_chunk : Counter(decouper(texte).tous) for id_chunk, texte in textes}
        self.longueurs = {id_chunk : sum(compte.values()) for id_chunk, compte in self.frequences.items()}
        self.longueur_moyenne = (sum(self.longueurs.values()) / len(self.longueurs)) if self.longueurs else 0.0
        self.chunks_par_terme = Counter(terme for compte in self.frequences.values() for terme in compte)

    def idf(self, terme : str) -> float :
        """rareté du terme : ln(1 + (N - n + 0,5) / (n + 0,5)), N chunks dont n contiennent le terme"""
        total, avec = len(self.longueurs), self.chunks_par_terme.get(terme, 0)
        return math.log(1 + (total - avec + 0.5) / (avec + 0.5))

    def scores(self, question : str, autorises : set[int] | None = None) -> list[ResultatLexical] :
        """chunks contenant un terme discriminant de la question, du meilleur score au moins bon.
        les modèles sont exclus (déjà un filtre) ; sans terme discriminant, aucun résultat (que des mots courants)"""
        termes = decouper(question)
        poids = {terme : self.idf(terme) * (POIDS_REFERENCE if terme in termes.references else 1.0)
                 for terme in set(termes.tous) - termes.modeles}
        plafond = max(1, self.part_discriminante * len(self.longueurs))      # au moins 1 chunk (petits index)
        discriminants = {terme for terme in poids if terme in termes.references or self.chunks_par_terme.get(terme, 0) <= plafond}
        resultats = []
        for id_chunk, compte in self.frequences.items() :
            if autorises is not None and id_chunk not in autorises :
                continue
            communs = [terme for terme in poids if terme in compte]
            if not any(terme in compte for terme in discriminants) :
                continue
            normalisation = K1 * (1 - B + B * self.longueurs[id_chunk] / self.longueur_moyenne)
            score = sum(poids[terme] * compte[terme] * (K1 + 1) / (compte[terme] + normalisation) for terme in communs)
            resultats.append(ResultatLexical(id_chunk, score, sorted(terme for terme in communs if terme in termes.references)))
        return sorted(resultats, key=lambda resultat : resultat.score, reverse=True)


## INDEX EN MÉMOIRE ##

_index : IndexLexical | None = None
_verrou = threading.Lock()          # l'API traite plusieurs requêtes en parallèle : un seul (re)calcul de l'index a la fois


def index_lexical(session : Session) -> IndexLexical :
    """l'index des chunks en base, reconstruit si les chunks ont changé depuis sa construction"""
    global _index
    version = version_des_chunks(session)
    with _verrou :
        if _index is None or _index.version != version :
            debut = time.perf_counter()
            # le chemin du fichier est indexé avec le texte : "PROC-WX-03" figure dans le nom de la procédure
            _index = IndexLexical([(id_chunk, f"{contenu}\n{source}") for id_chunk, contenu, source in textes_des_chunks(session)], version)
            logger.info("index lexical construit : %d chunks, %d termes en %.0f ms", len(_index.longueurs),
                        len(_index.chunks_par_terme), (time.perf_counter() - debut) * 1000)
    return _index


def rechercher_lexical(session : Session, texte : str, limite : int, modeles : list[str] | None = None,
                       categories : list[str] | None = None) -> list[ResultatLexical] :
    """les `limite` meilleurs chunks pour les termes du texte, avec les mêmes filtres que la recherche par vecteurs
    (modèles, droits de lecture)"""
    autorises = ids_chunks_filtres(session, modeles, categories) if modeles or categories is not None else None
    return index_lexical(session).scores(texte, autorises)[:limite]
