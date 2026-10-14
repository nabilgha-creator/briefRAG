"""métriques de la recherche du RAG (sans base ni modèle : fonctions pures, testées seules).

vocabulaire :
- besoin : un document qu'il faut retrouver pour bien répondre, écrit comme un motif de chemin
  ("Manuels/Manuel_WX-300.pdf", "Manuels/Manuel_WX-*.pdf") ; des alternatives séparées par "|" comptent pour un seul
  besoin ("Manuels/Manuel_FR-*.pdf | FAQ/faq-fours.html" : n'importe lequel suffit)
- acceptable : un document qui n'est pas indispensable mais contient aussi la réponse (le manuel, en plus de la
  procédure) : l'envoyer n'est pas une erreur
- rappel (recall) : part des besoins couverts par les extraits envoyés au LLM. 1 = rien ne manque
- précision : part des extraits envoyés qui viennent d'un document attendu ou acceptable. 1 = aucun extrait inutile
- rang du premier pertinent, et sa moyenne inverse (MRR) : un document utile arrive-t-il en tête ?
"""
from dataclasses import dataclass, field
from fnmatch import fnmatchcase


def alternatives(besoin : str) -> list[str] :
    return [motif.strip() for motif in besoin.split("|") if motif.strip()]


def satisfait(source : str, besoin : str) -> bool :
    """vrai si la source correspond a l'une des alternatives du besoin"""
    return any(fnmatchcase(source, motif) for motif in alternatives(besoin))


@dataclass
class ResultatQuestion :
    question : str
    besoins : list[str]
    sources : list[str]                       # sources des extraits envoyés au LLM, dans l'ordre
    couverts : list[str] = field(default_factory=list)
    manques : list[str] = field(default_factory=list)
    rappel : float = 0.0
    precision : float | None = None           # None : aucun extrait envoyé
    rang_premier : int | None = None          # 1 = le premier extrait est pertinent ; None = aucun
    fiches_attendues : list[str] = field(default_factory=list)
    fiches_trouvees : list[str] = field(default_factory=list)
    diagnostics : list[str] = field(default_factory=list)     # pourquoi un besoin manque (rempli par recall.py)

    @property
    def reussite(self) -> bool :
        """au moins un document attendu est envoyé au LLM"""
        return bool(self.couverts)

    @property
    def fiches_manquantes(self) -> list[str] :
        return [code for code in self.fiches_attendues if code not in self.fiches_trouvees]


def evaluer(question : str, besoins : list[str], sources : list[str], fiches_attendues : list[str] | None = None,
            fiches_trouvees : list[str] | None = None, acceptables : list[str] | None = None) -> ResultatQuestion :
    couverts = [besoin for besoin in besoins if any(satisfait(source, besoin) for source in sources)]
    utiles = besoins + (acceptables or [])
    pertinentes = [any(satisfait(source, besoin) for besoin in utiles) for source in sources]
    return ResultatQuestion(
        question=question, besoins=besoins, sources=sources,
        couverts=couverts, manques=[besoin for besoin in besoins if besoin not in couverts],
        rappel=len(couverts) / len(besoins) if besoins else 1.0,
        precision=sum(pertinentes) / len(sources) if sources else None,
        rang_premier=pertinentes.index(True) + 1 if any(pertinentes) else None,
        fiches_attendues=fiches_attendues or [], fiches_trouvees=fiches_trouvees or [],
    )


@dataclass
class Synthese :
    nombre : int
    rappel : float                    # moyenne des rappels (chaque question compte autant)
    reussite : float                  # part des questions avec au moins un bon document
    mrr : float                       # moyenne de 1 / rang du premier extrait pertinent (0 si aucun)
    precision : float | None          # moyenne sur les questions qui ont reçu des extraits
    extraits_moyens : float
    fiches : tuple[int, int]          # (trouvées, attendues)


def synthetiser(resultats : list[ResultatQuestion]) -> Synthese :
    if not resultats :
        return Synthese(0, 0.0, 0.0, 0.0, None, 0.0, (0, 0))
    precisions = [resultat.precision for resultat in resultats if resultat.precision is not None]
    attendues = sum(len(resultat.fiches_attendues) for resultat in resultats)
    trouvees = attendues - sum(len(resultat.fiches_manquantes) for resultat in resultats)
    return Synthese(
        nombre=len(resultats),
        rappel=sum(resultat.rappel for resultat in resultats) / len(resultats),
        reussite=sum(resultat.reussite for resultat in resultats) / len(resultats),
        mrr=sum(1 / resultat.rang_premier for resultat in resultats if resultat.rang_premier) / len(resultats),
        precision=sum(precisions) / len(precisions) if precisions else None,
        extraits_moyens=sum(len(resultat.sources) for resultat in resultats) / len(resultats),
        fiches=(trouvees, attendues),
    )
