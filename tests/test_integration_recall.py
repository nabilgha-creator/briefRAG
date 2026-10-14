"""qualité de la recherche sur la vraie base : le jeu de questions de référence (backend/evaluation/questions_recall.json)
ne doit pas régresser. mesure détaillée : python -m backend.evaluation.recall"""
import pytest

from backend.evaluation.metriques import synthetiser
from backend.evaluation.recall import charger_questions, evaluer_question, mesurer

pytestmark = pytest.mark.integration

RAPPEL_MIN = 0.95           # mesuré : 1,00 (octobre 2026)
PRECISION_MIN = 0.80        # mesuré : 0,90


@pytest.fixture(scope="module")
def resultats(base_disponible) :
    from backend.database.db import SessionLocal
    with SessionLocal() as session :
        return mesurer(session)


def test_rappel_du_jeu_de_reference(resultats) :
    synthese = synthetiser(resultats)
    manques = [f"{resultat.question} -> {diagnostic}" for resultat in resultats for diagnostic in resultat.diagnostics]
    assert synthese.rappel >= RAPPEL_MIN, "\n".join(manques)
    assert synthese.reussite == 1.0                   # chaque question reçoit au moins un bon document


def test_precision_du_jeu_de_reference(resultats) :
    assert synthetiser(resultats).precision >= PRECISION_MIN


def test_toutes_les_fiches_exactes(resultats) :
    assert all(not resultat.fiches_manquantes for resultat in resultats)


def test_doublons_ne_prennent_plus_toutes_les_places(session_bd) :
    """non-régression : le paragraphe sur les vibrations, identique dans les 6 manuels WX, évinçait la procédure"""
    element = next(element for element in charger_questions() if "vibre" in element["question"])
    assert evaluer_question(session_bd, element).rappel == 1.0
