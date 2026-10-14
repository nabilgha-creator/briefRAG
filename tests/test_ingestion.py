"""ingestion incrémentale : empreintes et choix des documents a retraiter, sans base"""
from backend.chargement import data
from backend.ingestion import a_traiter

REF = "Referentiel_codes_erreur.xlsx"
FICHIERS = {REF : "r1", "Manuels/WX-300.pdf" : "a1", "FAQ/faq.html" : "b1"}


def test_rien_n_a_change() :
    assert a_traiter(FICHIERS, dict(FICHIERS), REF) == (False, [])


def test_seul_le_document_modifie_ou_nouveau_est_retraite() :
    en_base = {REF : "r1", "Manuels/WX-300.pdf" : "a0"}               # WX-300 modifié, FAQ nouvelle
    assert a_traiter(FICHIERS, en_base, REF) == (False, ["Manuels/WX-300.pdf", "FAQ/faq.html"])


def test_referentiel_modifie_ou_option_tout_retraite_tout() :
    assert a_traiter(FICHIERS, {**FICHIERS, REF : "r0"}, REF) == (True, ["Manuels/WX-300.pdf", "FAQ/faq.html"])
    assert a_traiter(FICHIERS, dict(FICHIERS), REF, tout=True)[0]


def test_document_sans_empreinte_retraite() :
    """documents ingérés avant les empreintes (None en base)"""
    assert a_traiter(FICHIERS, {REF : "r1", "Manuels/WX-300.pdf" : None, "FAQ/faq.html" : "b1"}, REF) == (False, ["Manuels/WX-300.pdf"])


def test_empreinte_change_avec_le_contenu_ou_les_regles(tmp_path, monkeypatch) :
    fichier = tmp_path / "doc.pdf"
    fichier.write_bytes(b"version 1")
    premiere = data.empreinte_du_fichier(fichier)
    assert data.empreinte_du_fichier(fichier) == premiere and len(premiere) == 64
    fichier.write_bytes(b"version 2")
    assert data.empreinte_du_fichier(fichier) != premiere
    fichier.write_bytes(b"version 1")
    monkeypatch.setattr(data, "VERSION_DECOUPAGE", "autre version")     # nouvelles règles de découpage : tout est retraité
    assert data.empreinte_du_fichier(fichier) != premiere
