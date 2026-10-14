"""mesure du rappel de la recherche du RAG sur un jeu de questions de référence (questions_recall.json).

pour chaque question, la vraie recherche du chatbot est lancée (rechercher_contexte), puis les documents des extraits
envoyés au LLM sont comparés aux documents attendus (cf. metriques.py). aucun appel au LLM : gratuit et rapide.
pour chaque document attendu mais absent, le rapport dit pourquoi : écarté par le seuil de distance, classé trop
loin, écarté au dédoublonnage, ou exclu par le filtre des modèles.

lancement depuis la racine du projet :
    python -m backend.evaluation.recall                             réglages actuels
    python -m backend.evaluation.recall --seuil 0.6 --extraits 6    autres réglages, sans modifier le code
le rapport est aussi écrit en json dans assets/evaluation/, pour comparer les mesures dans le temps.
"""
import argparse
import json
import logging
import time
from dataclasses import asdict
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
            cause = f"classé trop loin (rang {rang}, distance {distance:.2f} ; {recherche.NB_EXTRAITS} extraits gardés)"
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
    print(f"\nRappel de la recherche : {synthese.nombre} questions (seuil {recherche.SEUIL_DISTANCE}, "
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


def enregistrer(resultats : list[ResultatQuestion], synthese : Synthese) -> Path :
    DOSSIER_RAPPORTS.mkdir(parents=True, exist_ok=True)
    chemin = DOSSIER_RAPPORTS / f"recall_{datetime.now():%Y%m%d-%H%M%S}.json"
    rapport = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "reglages": {"seuil_distance": recherche.SEUIL_DISTANCE, "nb_extraits": recherche.NB_EXTRAITS,
                     "nb_extraits_lies_aux_erreurs": recherche.NB_EXTRAITS_LIES_AUX_ERREURS},
        "synthese": asdict(synthese),
        "questions": [asdict(resultat) | {"reussite": resultat.reussite} for resultat in resultats],
    }
    chemin.write_text(json.dumps(rapport, indent=2, ensure_ascii=False), encoding="utf-8")
    return chemin


def main() -> None :
    parametres = argparse.ArgumentParser(description="mesure du rappel de la recherche du RAG")
    parametres.add_argument("--seuil", type=float, help=f"seuil de distance (actuel : {recherche.SEUIL_DISTANCE})")
    parametres.add_argument("--extraits", type=int, help=f"nombre d'extraits les plus proches (actuel : {recherche.NB_EXTRAITS})")
    arguments = parametres.parse_args()
    # réglages modifiés pour cette mesure seulement : rechercher_contexte lit ces valeurs a chaque appel
    if arguments.seuil is not None :
        recherche.SEUIL_DISTANCE = arguments.seuil
    if arguments.extraits is not None :
        recherche.NB_EXTRAITS = arguments.extraits

    debut = time.perf_counter()
    with SessionLocal() as session :
        resultats = mesurer(session)
    synthese = synthetiser(resultats)
    afficher(resultats, synthese)
    chemin = enregistrer(resultats, synthese)
    logger.info("rappel %.2f | réussite %.2f | MRR %.2f | précision %s | %d questions en %.0f s (seuil %s, %d extraits) | rapport %s",
                synthese.rappel, synthese.reussite, synthese.mrr, _nombre(synthese.precision), synthese.nombre,
                time.perf_counter() - debut, recherche.SEUIL_DISTANCE, recherche.NB_EXTRAITS, chemin.name)


if __name__ == "__main__" :
    from logger import configurer_logs

    configurer_logs(niveau_console=logging.WARNING)      # le rapport s'affiche ; les détails vont dans logs/briefrag.log
    main()
