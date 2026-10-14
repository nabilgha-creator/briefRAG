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

from backend.config import CATEGORIE_REFERENTIEL
from backend.database.crud import get_document_par_categorie, lister_erreurs, lister_modeles, rechercher_chunks
from backend.database.models import Chunk, Erreur, Modele
from backend.rag.embeddings import vectoriser_question

logger = logging.getLogger(__name__)

RE_CODE_ERREUR = re.compile(r"\b[Ee]\s?(\d{2})\b")       # E23, e23, E 23
NB_EXTRAITS = 5                                          # extraits les plus proches
NB_EXTRAITS_LIES_AUX_ERREURS = 3                         # extraits liés aux erreurs citées, en plus
SEUIL_DISTANCE = 0.55                                    # au-delà, un extrait est jugé hors sujet (distance cosinus ;
                                                         # calibré : pertinents 0.28-0.52, hors sujet 0.68 et plus)
MOTS_QUESTION_COURTE = 8                                 # en dessous, la question précédente est ajoutée a la recherche


@dataclass
class Appareils :
    """ce que la conversation dit des appareils concernés (une question peut en citer plusieurs)"""
    modele : str | None = None              # un seul modèle cité, sans autre appareil : WX-500
    type_appareil : str | None = None       # type(s) concerné(s) : "Lave-linge", "Lave-linge et Fours encastrables"
    modeles : list[str] = field(default_factory=list)     # modèles a considérer (filtre de recherche) ; vide = inconnu
    modeles_cites : list[str] = field(default_factory=list)   # modèles nommés dans la question


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
    id_chunk : int | None = None


@dataclass
class Reference :
    """une source citable dans la réponse (affichée dans le panneau des sources du front)"""
    numero : int
    titre : str
    source : str
    pages : list[int] = field(default_factory=list)
    extrait : str = ""                  # début du texte de la source
    distance : float | None = None      # distance cosinus a la question ; None = donnée exacte (fiche erreur)
    document : str | None = None        # fichier a ouvrir dans le lecteur (source du document) ; None = aucun
    id_chunk : int | None = None        # passage a surligner dans ce fichier (extraits seulement)


@dataclass
class Contexte :
    appareils : Appareils
    codes : list[str]
    fiches : list[FicheErreur]
    extraits : list[Extrait]
    source_referentiel : str | None = None      # fichier du référentiel, ouvert par le lecteur pour une fiche erreur

    @property
    def besoin_precision(self) -> bool :
        """un code erreur sans appareil connu : sa signification dépend du modèle, il faut le demander"""
        return bool(self.codes) and not self.appareils.modeles

    def references(self) -> list[Reference] :
        fiches = [Reference(fiche.numero, f"Référentiel des codes erreur — fiche {fiche.code}", "table erreur",
                            extrait=f"{fiche.signification}. Intervention : {fiche.intervention}", document=self.source_referentiel)
                  for fiche in self.fiches]
        return fiches + [Reference(extrait.numero, extrait.titre_document, extrait.source, extrait.pages,
                                   extrait=_apercu(extrait.contenu), distance=round(extrait.distance, 3),
                                   document=extrait.source, id_chunk=extrait.id_chunk) for extrait in self.extraits]


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
    """textes du plus récent au plus ancien (la question puis les messages précédents) : le premier qui cite
    un appareil l'emporte, avec TOUS les modèles et types qu'il cite ("lave-linge et fours" -> les deux gammes).
    un type n'est étendu a toute sa gamme que si aucun modèle de ce type n'est cité ("mon lave-linge WX-500" -> WX-500)"""
    types = sorted({modele.type for modele in modeles if modele.type})
    for texte in textes :
        cites = [modele for modele in modeles if _motif_modele(modele.modele).search(texte)]
        types_cites = [type_appareil for type_appareil in types if _motif_type(type_appareil).search(texte)]
        if not cites and not types_cites :
            continue
        types_a_etendre = [type_appareil for type_appareil in types_cites if all(modele.type != type_appareil for modele in cites)]
        a_considerer = [modele.modele for modele in cites] + [modele.modele for modele in modeles if modele.type in types_a_etendre]
        types_concernes = list(dict.fromkeys([modele.type for modele in cites if modele.type] + types_a_etendre))
        return Appareils(modele=cites[0].modele if len(cites) == 1 and not types_a_etendre else None,
                         type_appareil=" et ".join(types_concernes) or None,
                         modeles=a_considerer, modeles_cites=[modele.modele for modele in cites])
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


def _rechercher_equilibre(session : Session, vecteur : list[float], a_considerer : list[str], modeles : list[Modele],
                          categories : list[str] | None) -> list[tuple[Chunk, float]] :
    """extraits les plus proches. si la question couvre plusieurs types d'appareils ("lave-linge et fours"),
    chaque type a son propre lot : sinon le type dont les textes ressemblent le plus a la question prend toute la place"""
    type_du_modele = {modele.modele : modele.type for modele in modeles}
    groupes : dict[str | None, list[str]] = {}
    for nom in a_considerer :
        groupes.setdefault(type_du_modele.get(nom), []).append(nom)
    if len(groupes) <= 1 :
        return rechercher_chunks(session, vecteur, NB_EXTRAITS, modeles=a_considerer or None, categories=categories)
    par_groupe = max(2, -(-NB_EXTRAITS // len(groupes)))       # arrondi au supérieur
    return [paire for noms in groupes.values()
            for paire in rechercher_chunks(session, vecteur, par_groupe, modeles=noms, categories=categories)]


def _texte_de_recherche(question : str, questions_precedentes : list[str]) -> str :
    """une question courte ("et comment je fais ?") dépend de la précédente : on les cherche ensemble"""
    if questions_precedentes and len(question.split()) < MOTS_QUESTION_COURTE :
        return f"{questions_precedentes[-1]}\n{question}"
    return question


def rechercher_contexte(session : Session, question : str, questions_precedentes : list[str],
                        categories : list[str] | None = None) -> Contexte :
    """questions_precedentes : les messages précédents de l'utilisateur, du plus ancien au plus récent.
    categories : catégories de documents que l'utilisateur peut consulter (None = toutes) ; les fiches erreur
    exactes suivent la catégorie du référentiel des codes erreur"""
    plus_recentes_d_abord = [question] + questions_precedentes[::-1]
    modeles = lister_modeles(session)
    appareils = analyser_appareils(plus_recentes_d_abord, modeles)
    codes = next((codes for texte in plus_recentes_d_abord if (codes := extraire_codes(texte))), [])
    if codes and not appareils.modeles :
        appareils = _appareils_des_codes(session, codes, modeles)

    fiches, ids_erreurs = [], []
    referentiel_autorise = categories is None or CATEGORIE_REFERENTIEL in categories
    if codes and appareils.modeles and referentiel_autorise :
        for code in codes :
            erreurs = lister_erreurs(session, code, appareils.modeles)
            if not erreurs :
                logger.info("code %s inconnu pour %s", code, appareils.modele or appareils.type_appareil)
            fiches.extend(_fiches(erreurs, code, premier_numero=len(fiches) + 1))
            ids_erreurs.extend(erreur.id_erreur for erreur in erreurs)

    vecteur = vectoriser_question(_texte_de_recherche(question, questions_precedentes))
    filtre = appareils.modeles or None
    proches = _rechercher_equilibre(session, vecteur, appareils.modeles, modeles, categories)
    lies = (rechercher_chunks(session, vecteur, NB_EXTRAITS_LIES_AUX_ERREURS, modeles=filtre, ids_erreurs=ids_erreurs, categories=categories)
            if ids_erreurs else [])

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
                        chunk.contenu, distance, chunk.id_chunk)
                for index, (chunk, distance) in enumerate(ordonnes)]
    referentiel = get_document_par_categorie(session, CATEGORIE_REFERENTIEL) if fiches else None

    logger.info("contexte : appareil %s | codes %s | %d fiche(s) | %d extrait(s) (distances %s)",
                appareils.modele or appareils.type_appareil or "inconnu", codes or "-", len(fiches), len(extraits),
                [round(extrait.distance, 2) for extrait in extraits])
    return Contexte(appareils=appareils, codes=codes, fiches=fiches, extraits=extraits,
                    source_referentiel=referentiel.source if referentiel else None)
