"""recherche du contexte sur la vraie base (documentation ingérée) : appareils, fiches exactes, droits. sans LLM"""
import pytest

from backend.rag.assistant import preparer
from backend.rag.prompts import MESSAGE_PRECISION_MODELE
from backend.rag.recherche import rechercher_contexte

pytestmark = pytest.mark.integration


def _sources(contexte) -> set[str] :
    return {extrait.source for extrait in contexte.extraits}


def test_question_sur_deux_types_couvre_les_deux(session_bd) :
    """non-régression : "lave-linge et fours" ne renvoyait que des documents de fours"""
    contexte = rechercher_contexte(session_bd, "Comment résoudre les codes erreur fréquents sur les lave-linge et fours", [])
    sources = _sources(contexte)
    assert any("WX" in source or "lave-linge" in source for source in sources)
    assert any("FR" in source or "fours" in source for source in sources)


def test_piege_e23_selon_l_appareil(session_bd) :
    lave_vaisselle = rechercher_contexte(session_bd, "Que veut dire E23 sur un LV-200 ?", [])
    lave_linge = rechercher_contexte(session_bd, "Que veut dire E23 sur un WX-500 ?", [])
    assert "sonde" in lave_vaisselle.fiches[0].signification.lower()
    assert "pompe" in lave_linge.fiches[0].signification.lower()


def test_bulletin_technique_remonte_pour_e52_wx500(session_bd) :
    contexte = rechercher_contexte(session_bd, "Le client a un E52 sur son WX-500", [])
    assert any("BT-2026-007" in source for source in _sources(contexte))


def test_fiche_erreur_oriente_la_recherche(session_bd) :
    """E05 du FR-600 = « verrouillage de porte pyrolyse » : la procédure qui dit que le FR-600 n'a pas de pyrolyse
    doit remonter (contradiction à signaler), sans les lignes du référentiel des autres codes"""
    contexte = rechercher_contexte(session_bd, "Mon FR-600 affiche E05, que faire ?", [])
    sources = _sources(contexte)
    assert any("PROC-FR-01" in source for source in sources)
    assert not any("Referentiel" in source for source in sources)


def test_extraits_filtres_sur_le_modele(session_bd) :
    contexte = rechercher_contexte(session_bd, "Comment nettoyer le filtre de vidange de mon WX-300 ?", [])
    manuels = [source for source in _sources(contexte) if source.startswith("Manuels/")]
    assert manuels and all("WX-300" in manuel for manuel in manuels)


def test_code_propre_a_une_gamme_deduit_l_appareil(session_bd) :
    contexte = rechercher_contexte(session_bd, "Que signifie le code E15 ?", [])
    assert contexte.appareils.type_appareil == "Lave-vaisselle" and not contexte.besoin_precision


def test_code_present_dans_plusieurs_gammes_fait_demander_le_modele(session_bd) :
    preparation = preparer(session_bd, "Que veut dire le code E23 ?", [])
    assert preparation.messages is None and preparation.reponse_directe == MESSAGE_PRECISION_MODELE


def test_droits_role_limite_a_la_faq(session_bd) :
    contexte = rechercher_contexte(session_bd, "Mon WX-500 affiche E52, que faire ?", [], categories=["FAQ"])
    assert contexte.extraits and all(source.startswith("FAQ/") for source in _sources(contexte))
    assert contexte.fiches == []              # fiches exactes réservées a la catégorie du référentiel


def test_aucun_droit_aucune_source(session_bd) :
    contexte = rechercher_contexte(session_bd, "Mon WX-500 affiche E52, que faire ?", [], categories=[])
    assert contexte.extraits == [] and contexte.fiches == []


def test_reference_de_piece_trouvee_par_les_termes(session_bd) :
    """les vecteurs seuls écartaient ces documents (distance 0,59 > seuil) : la référence exacte les ramène"""
    contexte = rechercher_contexte(session_bd, "À quoi correspond la pièce 44-3311 ?", [])
    assert {"Bulletins_techniques/BT-2026-007.docx", "Referentiel_codes_erreur.xlsx"} & _sources(contexte)


def test_recherche_lexicale_respecte_les_droits(session_bd) :
    contexte = rechercher_contexte(session_bd, "Le technicien doit-il contrôler le relais K2 ?", [], categories=["FAQ"])
    assert all(source.startswith("FAQ/") for source in _sources(contexte))


def test_relance_sans_sujet_cherche_avec_la_question_precedente(session_bd) :
    """non-régression : une relance qui ne parle pas du sujet (> 8 mots) ne trouvait aucun extrait"""
    contexte = rechercher_contexte(session_bd, "d'accord, ce n'est pas pour moi mais pour ma belle-mère",
                                   ["La porte du four est bloquée après la cuisson, que faire ?"])
    assert "FAQ/faq-fours.html" in _sources(contexte)
