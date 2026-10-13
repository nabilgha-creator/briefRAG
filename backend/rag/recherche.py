"""recherche du contexte d'une question, sans LLM :
1. analyse : modèle (ou a défaut type d'appareil) et codes erreur, dans la question ou plus tôt dans la conversation
2. fiches erreur exactes, lues dans la table erreur (fiables, pas d'approximation)
3. extraits de documentation proches de la question (recherche par vecteurs), filtrés sur les modèles concernés,
   plus les extraits liés aux erreurs citées (un bulletin technique sur E52 remonte toujours pour une question sur E52)
"""
import logging
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.database.crud import lister_erreurs, lister_modeles, rechercher_chunks
from backend.database.models import Chunk, Erreur, Modele
from backend.rag.embeddings import vectoriser_question

logger = logging.getLogger(__name__)

RE_CODE_ERREUR = re.compile(r"\b[Ee]\s?(\d{2})\b")     # E23, e23, E 23
NB_EXTRAITS = 5                                          # extraits les plus proches
NB_EXTRAITS_LIES_AUX_ERREURS = 3                         # extraits liés aux erreurs citées, en plus
SEUIL_DISTANCE = 0.55                                    # au-delà, un extrait est jugé hors sujet (distance cosinus ;
                                                         # calibré : pertinents 0.28-0.52, hors sujet 0.68 et plus)
MOTS_QUESTION_COURTE = 8                                 # en dessous, la question précédente est ajoutée a la recherche


@dataclass
class Appareils :
    """ce que la conversation dit de l'appareil concerné"""
    modele : str | None = None              # WX-500
    type_appareil : str | None = None       # Lave-linge
    modeles : list[str] = field(default_factory=list)     # modèles a considérer : le modèle, ou tous ceux du type ; vide = inconnu


@dataclass
class FicheErreur :
    numero : int
    code : str
    signification : str
    conduite : str
    intervention : str
    modeles : list[str]


@dataclass
class Extrait :
    numero : int
    titre_document : str
    source : str
    pages : list[int]
    contenu : str
    distance : float


@dataclass
class Reference :
    """une source citable dans la réponse (affichée dans le panneau des sources du front)"""
    numero : int
    titre : str
    source : str
    pages : list[int] = field(default_factory=list)
    extrait : str = ""                  # début du texte de la source
    distance : float | None = None      # distance cosinus a la question ; None = donnée exacte (fiche erreur)


@dataclass
class Contexte :
    appareils : Appareils
    codes : list[str]
    fiches : list[FicheErreur]
    extraits : list[Extrait]

    @property
    def besoin_precision(self) -> bool :
        """un code erreur sans appareil connu : sa signification dépend du modèle, il faut le demander"""
        return bool(self.codes) and not self.appareils.modeles

    def references(self) -> list[Reference] :
        fiches = [Reference(fiche.numero, f"Référentiel des codes erreur — fiche {fiche.code}", "table erreur",
                            extrait=f"{fiche.signification}. Intervention : {fiche.intervention}") for fiche in self.fiches]
        return fiches + [Reference(extrait.numero, extrait.titre_document, extrait.source, extrait.pages,
                                   extrait=_apercu(extrait.contenu), distance=round(extrait.distance, 3)) for extrait in self.extraits]


TAILLE_APERCU = 220


def _apercu(contenu : str) -> str :
    """début du texte d'un chunk, sans sa 1re ligne de contexte ("[type] titre du document")"""
    texte = " ".join(contenu.split("\n", 1)[-1].split())
    return texte if len(texte) <= TAILLE_APERCU else texte[:TAILLE_APERCU].rsplit(" ", 1)[0] + "…"


## ANALYSE DE LA QUESTION ##

def _motif_modele(nom : str) -> re.Pattern[str] :
    """WX-500 est aussi reconnu écrit "wx500" ou "WX 500" """
    prefixe, _, numero = nom.partition("-")
    return re.compile(rf"\b{re.escape(prefixe)}[\s-]?{re.escape(numero)}\b", re.IGNORECASE)


def _motif_type(type_appareil : str) -> re.Pattern[str] :
    """"Fours encastrables" -> four(s), "Lave-linge" -> lave-linge(s)"""
    mot = type_appareil.split()[0].lower()
    mot = mot[:-1] if mot.endswith("s") else mot
    return re.compile(rf"\b{re.escape(mot)}s?\b", re.IGNORECASE)


def analyser_appareils(textes : list[str], modeles : list[Modele]) -> Appareils :
    """textes du plus récent au plus ancien (la question puis les messages précédents) :
    le premier qui cite un modèle, ou a défaut un type d'appareil, l'emporte"""
    types = sorted({modele.type for modele in modeles if modele.type})
    for texte in textes :
        for modele in modeles :
            if _motif_modele(modele.modele).search(texte) :
                return Appareils(modele=modele.modele, type_appareil=modele.type, modeles=[modele.modele])
        for type_appareil in types :
            if _motif_type(type_appareil).search(texte) :
                return Appareils(type_appareil=type_appareil,
                                 modeles=[modele.modele for modele in modeles if modele.type == type_appareil])
    return Appareils()


def extraire_codes(texte : str) -> list[str] :
    return sorted({f"E{numero}" for numero in RE_CODE_ERREUR.findall(texte)})


## RECHERCHE ##

def _fiches(erreurs : list[Erreur], code : str, premier_numero : int) -> list[FicheErreur] :
    """une fiche par signification différente : les modèles qui partagent la même définition sont regroupés"""
    groupes : dict[tuple[str, str, str], list[str]] = {}
    for erreur in erreurs :
        groupes.setdefault((erreur.signification, erreur.conduite, erreur.intervention), []).append(erreur.modele)
    return [FicheErreur(premier_numero + index, code, signification, conduite, intervention, modeles)
            for index, ((signification, conduite, intervention), modeles) in enumerate(groupes.items())]


def _appareils_des_codes(session : Session, codes : list[str], modeles : list[Modele]) -> Appareils :
    """un code qui n'existe que pour un seul type d'appareil désigne ce type (E15 : lave-vaisselle uniquement) :
    inutile alors de demander le modèle"""
    type_du_modele = {modele.modele : modele.type for modele in modeles}
    types = {type_du_modele[erreur.modele] for code in codes for erreur in lister_erreurs(session, code, list(type_du_modele))}
    if len(types) != 1 :
        return Appareils()
    type_appareil = types.pop()
    return Appareils(type_appareil=type_appareil, modeles=[modele.modele for modele in modeles if modele.type == type_appareil])


def _texte_de_recherche(question : str, questions_precedentes : list[str]) -> str :
    """une question courte ("et comment je fais ?") dépend de la précédente : on les cherche ensemble"""
    if questions_precedentes and len(question.split()) < MOTS_QUESTION_COURTE :
        return f"{questions_precedentes[-1]}\n{question}"
    return question


def rechercher_contexte(session : Session, question : str, questions_precedentes : list[str]) -> Contexte :
    """questions_precedentes : les messages précédents de l'utilisateur, du plus ancien au plus récent"""
    plus_recentes_d_abord = [question] + questions_precedentes[::-1]
    modeles = lister_modeles(session)
    appareils = analyser_appareils(plus_recentes_d_abord, modeles)
    codes = next((codes for texte in plus_recentes_d_abord if (codes := extraire_codes(texte))), [])
    if codes and not appareils.modeles :
        appareils = _appareils_des_codes(session, codes, modeles)

    fiches, ids_erreurs = [], []
    if codes and appareils.modeles :
        for code in codes :
            erreurs = lister_erreurs(session, code, appareils.modeles)
            if not erreurs :
                logger.info("code %s inconnu pour %s", code, appareils.modele or appareils.type_appareil)
            fiches.extend(_fiches(erreurs, code, premier_numero=len(fiches) + 1))
            ids_erreurs.extend(erreur.id_erreur for erreur in erreurs)

    vecteur = vectoriser_question(_texte_de_recherche(question, questions_precedentes))
    filtre = appareils.modeles or None
    proches = rechercher_chunks(session, vecteur, NB_EXTRAITS, modeles=filtre)
    lies = rechercher_chunks(session, vecteur, NB_EXTRAITS_LIES_AUX_ERREURS, modeles=filtre, ids_erreurs=ids_erreurs) if ids_erreurs else []

    # les extraits liés aux erreurs sont pertinents par construction ; les autres doivent passer le seuil.
    # écartés pour économiser des tokens : un extrait qui répète une fiche erreur déjà fournie (ligne du référentiel),
    # et un texte identique a un extrait déjà retenu (même paragraphe dans les manuels de plusieurs modèles)
    deja_fournis = [f"{fiche.code} — {fiche.signification}" for fiche in fiches]
    retenus : dict[int, tuple[Chunk, float]] = {}
    textes_vus : set[str] = set()
    candidats = lies + [(chunk, distance) for chunk, distance in proches if distance <= SEUIL_DISTANCE]
    for chunk, distance in sorted(candidats, key=lambda paire : paire[1]) :
        texte_sans_titre = chunk.contenu.split("\n", 1)[-1]
        if chunk.id_chunk in retenus or texte_sans_titre in textes_vus or any(ligne in chunk.contenu for ligne in deja_fournis) :
            continue
        retenus[chunk.id_chunk] = (chunk, distance)
        textes_vus.add(texte_sans_titre)
    ordonnes = list(retenus.values())
    extraits = [Extrait(len(fiches) + index + 1, chunk.rel_document.titre, chunk.rel_document.source, chunk.pages or [],
                        chunk.contenu, distance)
                for index, (chunk, distance) in enumerate(ordonnes)]

    logger.info("contexte : appareil %s | codes %s | %d fiche(s) | %d extrait(s) (distances %s)",
                appareils.modele or appareils.type_appareil or "inconnu", codes or "-", len(fiches), len(extraits),
                [round(extrait.distance, 2) for extrait in extraits])
    return Contexte(appareils=appareils, codes=codes, fiches=fiches, extraits=extraits)
