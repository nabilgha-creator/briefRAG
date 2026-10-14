"""métriques de l'évaluation de la recherche (rappel, précision, MRR), sans base"""
import pytest

from backend.evaluation.metriques import evaluer, satisfait, synthetiser


@pytest.mark.parametrize("source, besoin, attendu", [
    ("Manuels/Manuel_WX-300.pdf", "Manuels/Manuel_WX-300.pdf", True),
    ("Manuels/Manuel_WX-500.pdf", "Manuels/Manuel_WX-*.pdf", True),            # motif
    ("Manuels/Manuel_LV-200.pdf", "Manuels/Manuel_WX-*.pdf", False),
    ("FAQ/faq-fours.html", "Manuels/Manuel_FR-*.pdf | FAQ/faq-fours.html", True),  # l'une des alternatives
])
def test_un_document_satisfait_un_besoin(source, besoin, attendu) :
    assert satisfait(source, besoin) is attendu


def test_rappel_precision_et_rang() :
    resultat = evaluer("question", besoins=["A.pdf", "B.docx"], sources=["X.pdf", "A.pdf", "Y.html", "A.pdf"],
                       acceptables=["Y.html"])
    assert (resultat.couverts, resultat.manques) == (["A.pdf"], ["B.docx"])
    assert resultat.rappel == 0.5                      # 1 besoin sur 2
    assert resultat.precision == 0.75                  # 3 extraits utiles sur 4 (A, Y acceptable, A)
    assert resultat.rang_premier == 2 and resultat.reussite


def test_aucun_extrait_envoye() :
    resultat = evaluer("question", besoins=["A.pdf"], sources=[], fiches_attendues=["E23"], fiches_trouvees=[])
    assert (resultat.rappel, resultat.precision, resultat.rang_premier, resultat.reussite) == (0.0, None, None, False)
    assert resultat.fiches_manquantes == ["E23"]


def test_synthese() :
    resultats = [evaluer("q1", ["A"], ["A", "X"]), evaluer("q2", ["B"], ["X", "B"], ["E15"], ["E15"]), evaluer("q3", ["C"], [])]
    synthese = synthetiser(resultats)
    assert synthese.rappel == pytest.approx(2 / 3)
    assert synthese.reussite == pytest.approx(2 / 3)
    assert synthese.mrr == pytest.approx((1 + 1 / 2 + 0) / 3)       # rangs 1, 2, aucun
    assert synthese.precision == pytest.approx(0.5)                 # q3 sans extrait : non comptée
    assert synthese.fiches == (1, 1)
