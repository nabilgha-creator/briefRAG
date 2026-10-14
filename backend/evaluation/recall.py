"""mesure du rappel de la recherche du RAG sur un jeu de questions de référence (questions_recall.json).

pour chaque question, la vraie recherche du chatbot est lancée (rechercher_contexte), puis les documents des extraits
envoyés au LLM sont comparés aux documents attendus (cf. metriques.py). aucun appel au LLM : gratuit et rapide.
pour chaque document attendu mais absent, le rapport dit pourquoi : écarté par le seuil de distance, classé trop
loin, écarté au dédoublonnage, ou exclu par le filtre des modèles.

lancement depuis la racine du projet :
    python -m backend.evaluation.recall                             réglages actuels
    python -m backend.evaluation.recall --seuil 0.6 --extraits 6    autres réglages, sans modifier le code
    python -m backend.evaluation.recall --sans-lexicale             recherche par vecteurs seule (pour comparer)
les résultats sont enregistrés en csv dans assets/evaluation/ (séparateur « ; », virgule décimale : s'ouvre dans Excel) :
- recall_<date>.csv : le détail, une ligne par question
- historique_recall.csv : une ligne par mesure (réglages et synthèse), pour suivre l'évolution
"""
import argparse
import csv
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.config import ASSETS
from backend.database.crud import rechercher_chunks
from backend.database.db import SessionLocal
from backend.evaluation.metriques import ResultatQuestion, Synthese, evaluer, satisfait, synthetiser
from backend.rag import recherche
from backend.rag.embeddings import vectoriser_question

logger = logging.getLogger(__name__)

FICHIER_QUESTIONS = Path(__file__).with_name("questions_recall.json")
DOSSIER_RAPPORTS = ASSETS / "evaluation"
PROFONDEUR_DIAGNOSTIC = 50          # extraits examinés pour expliquer un document manquant
FICHIER_HISTORIQUE = DOSSIER_RAPPORTS / "historique_recall.csv"
SEPARATEUR = ";"                     # Excel en français : « ; » sépare les colonnes, « , » est la virgule décimale
ENCODAGE = "utf-8-sig"               # avec l'indicateur d'encodage (BOM) : Excel affiche les accents correctement


def charger_questions(chemin : Path = FICHIER_QUESTIONS) -> list[dict] :
    return json.loads(chemin.read_text(encoding="utf-8"))["questions"]


def _diagnostic(session : Session, question : str, historique : list[str], modeles : list[str], besoin : str) -> str :
    """pourquoi un document attendu manque : on cherche son meilleur extrait sans seuil ni limite"""
    vecteur = vectoriser_question(recherche.texte_de_recherche(question, historique))
    for rang, (chunk, distance) in enumerate(rechercher_chunks(session, vecteur, PROFONDEUR_DIAGNOSTIC, modeles=modeles or None), 1) :
        if not satisfait(chunk.rel_document.source, besoin) :
            continue
        if distance > recherche.SEUIL_DISTANCE :
            cause = f"écarté par le seuil (distance {distance:.2f} > {recherche.SEUIL_DISTANCE})"
        elif rang > recherche.NB_EXTRAITS :
            cause = f"classé trop loin (rang {rang} par vecteurs, distance {distance:.2f} ; {recherche.NB_EXTRAITS} extraits gardés)"
        else :
            cause = f"rang {rang}, distance {distance:.2f}, mais écarté au dédoublonnage ou par la répartition entre appareils"
        return f"{besoin} : {cause}"
    filtre = ", ".join(modeles) if modeles else "aucun"
    return f"{besoin} : aucun extrait parmi les {PROFONDEUR_DIAGNOSTIC} plus proches (filtre des modèles : {filtre})"


def evaluer_question(session : Session, element : dict) -> ResultatQuestion :
    question, historique = element["question"], element.get("historique", [])
    contexte = recherche.rechercher_contexte(session, question, historique)
    resultat = evaluer(question, element["documents"], [extrait.source for extrait in contexte.extraits],
                       element.get("fiches", []), sorted({fiche.code for fiche in contexte.fiches}), element.get("acceptables", []))
    resultat.theme = element.get("theme", "")
    if contexte.besoin_precision :
        resultat.diagnostics.append("code erreur sans appareil : l'assistant demanderait le modèle")
    resultat.diagnostics += [_diagnostic(session, question, historique, contexte.appareils.modeles, besoin) for besoin in resultat.manques]
    return resultat


def mesurer(session : Session, questions : list[dict] | None = None) -> list[ResultatQuestion] :
    return [evaluer_question(session, element) for element in (questions or charger_questions())]


## RAPPORT ##

def _nombre(valeur : float | None) -> str :
    return "-" if valeur is None else f"{valeur:.2f}".replace(".", ",")


def _ligne(numero : int, resultat : ResultatQuestion) -> str :
    pertinents = round(resultat.precision * len(resultat.sources)) if resultat.precision is not None else 0
    fiches = "-" if not resultat.fiches_attendues else ("ok" if not resultat.fiches_manquantes else "MANQUE " + ",".join(resultat.fiches_manquantes))
    return (f"{numero:>3}  {len(resultat.couverts)}/{len(resultat.besoins):<5} {pertinents}/{len(resultat.sources):<8} "
            f"{resultat.rang_premier or '-':<6} {fiches:<9} {resultat.question}")


def afficher(resultats : list[ResultatQuestion], synthese : Synthese) -> None :
    mode = "vecteurs + lexicale" if recherche.RECHERCHE_LEXICALE else "vecteurs seuls"
    print(f"\nRappel de la recherche : {synthese.nombre} questions ({mode}, seuil {recherche.SEUIL_DISTANCE}, "
          f"{recherche.NB_EXTRAITS} extraits + {recherche.NB_EXTRAITS_LIES_AUX_ERREURS} liés aux codes erreur)\n")
    print("  #  rappel précision  1er    fiches    question")
    for numero, resultat in enumerate(resultats, 1) :
        print(_ligne(numero, resultat))
        for diagnostic in resultat.diagnostics :
            print(f"       manque  {diagnostic}")
    trouvees, attendues = synthese.fiches
    print(f"""
Synthèse
  rappel moyen      {_nombre(synthese.rappel)}   part des documents attendus envoyés au LLM (1 = rien ne manque)
  réussite          {round(synthese.reussite * synthese.nombre)}/{synthese.nombre}   questions avec au moins un bon document
  MRR               {_nombre(synthese.mrr)}   1 = le premier extrait est toujours un document utile
  précision         {_nombre(synthese.precision)}   part des extraits envoyés qui viennent d'un document attendu ou acceptable
  extraits envoyés  {_nombre(synthese.extraits_moyens)} en moyenne par question
  fiches exactes    {trouvees}/{attendues}
""")


def _decimal(valeur : float | None) -> str :
    return "" if valeur is None else f"{valeur:.3f}".replace(".", ",")


def _liste(valeurs : list[str]) -> str :
    return " | ".join(valeurs)


def reglages() -> dict[str, object] :
    """réglages de la recherche au moment de la mesure"""
    return {"seuil_distance": _decimal(recherche.SEUIL_DISTANCE), "nb_extraits": recherche.NB_EXTRAITS,
            "nb_extraits_lies_aux_erreurs": recherche.NB_EXTRAITS_LIES_AUX_ERREURS,
            "candidats_par_extrait": recherche.CANDIDATS_PAR_EXTRAIT,
            "recherche_lexicale": "oui" if recherche.RECHERCHE_LEXICALE else "non", "rrf_k": recherche.RRF_K}


def _ecrire_detail(chemin : Path, resultats : list[ResultatQuestion]) -> None :
    with open(chemin, "w", newline="", encoding=ENCODAGE) as fichier :
        ecriture = csv.writer(fichier, delimiter=SEPARATEUR)
        ecriture.writerow(["numero", "theme", "question", "rappel", "precision", "rang_premier_pertinent", "reussite",
                           "documents_attendus", "documents_manquants", "sources_envoyees", "fiches_attendues",
                           "fiches_manquantes", "diagnostics"])
        for numero, resultat in enumerate(resultats, 1) :
            ecriture.writerow([numero, resultat.theme, resultat.question, _decimal(resultat.rappel), _decimal(resultat.precision),
                               resultat.rang_premier or "", "oui" if resultat.reussite else "non", _liste(resultat.besoins),
                               _liste(resultat.manques), _liste(resultat.sources), _liste(resultat.fiches_attendues),
                               _liste(resultat.fiches_manquantes), _liste(resultat.diagnostics)])


def _ajouter_historique(ligne : dict[str, object]) -> None :
    """ajoute une ligne a l'historique ; si de nouveaux réglages apparaissent, les colonnes sont complétées
    (les anciennes mesures gardent une case vide)"""
    anciennes, colonnes = [], list(ligne)
    if FICHIER_HISTORIQUE.exists() :
        with open(FICHIER_HISTORIQUE, newline="", encoding=ENCODAGE) as fichier :
            lecture = csv.DictReader(fichier, delimiter=SEPARATEUR)
            anciennes = list(lecture)
            colonnes = list(dict.fromkeys([*(lecture.fieldnames or []), *ligne]))
    with open(FICHIER_HISTORIQUE, "w", newline="", encoding=ENCODAGE) as fichier :
        ecriture = csv.DictWriter(fichier, fieldnames=colonnes, delimiter=SEPARATEUR, restval="")
        ecriture.writeheader()
        ecriture.writerows([*anciennes, ligne])


def enregistrer(resultats : list[ResultatQuestion], synthese : Synthese) -> Path :
    """écrit le détail de la mesure et l'ajoute a l'historique ; renvoie le chemin du détail"""
    DOSSIER_RAPPORTS.mkdir(parents=True, exist_ok=True)
    maintenant = datetime.now()
    detail = DOSSIER_RAPPORTS / f"recall_{maintenant:%Y%m%d-%H%M%S}.csv"
    _ecrire_detail(detail, resultats)
    trouvees, attendues = synthese.fiches
    _ajouter_historique({"date": f"{maintenant:%Y-%m-%d %H:%M:%S}", **reglages(), "questions": synthese.nombre,
                         "rappel": _decimal(synthese.rappel), "reussite": _decimal(synthese.reussite), "mrr": _decimal(synthese.mrr),
                         "precision": _decimal(synthese.precision), "extraits_moyens": _decimal(synthese.extraits_moyens),
                         "fiches_trouvees": trouvees, "fiches_attendues": attendues, "detail": detail.name})
    return detail


def main() -> None :
    parametres = argparse.ArgumentParser(description="mesure du rappel de la recherche du RAG")
    parametres.add_argument("--seuil", type=float, help=f"seuil de distance (actuel : {recherche.SEUIL_DISTANCE})")
    parametres.add_argument("--extraits", type=int, help=f"nombre d'extraits les plus proches (actuel : {recherche.NB_EXTRAITS})")
    parametres.add_argument("--sans-lexicale", action="store_true", help="recherche par vecteurs seule, sans la recherche lexicale")
    arguments = parametres.parse_args()
    # réglages modifiés pour cette mesure seulement : rechercher_contexte lit ces valeurs a chaque appel
    if arguments.seuil is not None :
        recherche.SEUIL_DISTANCE = arguments.seuil
    if arguments.extraits is not None :
        recherche.NB_EXTRAITS = arguments.extraits
    if arguments.sans_lexicale :
        recherche.RECHERCHE_LEXICALE = False

    debut = time.perf_counter()
    with SessionLocal() as session :
        resultats = mesurer(session)
    synthese = synthetiser(resultats)
    afficher(resultats, synthese)
    chemin = enregistrer(resultats, synthese)
    print(f"Résultats enregistrés : {chemin}")
    print(f"Historique des mesures : {FICHIER_HISTORIQUE}\n")
    logger.info("rappel %.2f | réussite %.2f | MRR %.2f | précision %s | %d questions en %.0f s (seuil %s, %d extraits) | rapport %s",
                synthese.rappel, synthese.reussite, synthese.mrr, _nombre(synthese.precision), synthese.nombre,
                time.perf_counter() - debut, recherche.SEUIL_DISTANCE, recherche.NB_EXTRAITS, chemin.name)


if __name__ == "__main__" :
    from logger import configurer_logs

    configurer_logs(niveau_console=logging.WARNING)      # le rapport s'affiche ; les détails vont dans logs/briefrag.log
    main()
