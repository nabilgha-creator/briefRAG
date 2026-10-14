"""chargement de la documentation : métadonnées, FAQ html, référentiel excel, nettoyage du texte"""
import openpyxl
import pytest

from backend.chargement.data import _construire_chunk, _extraire_version, _modeles_du_document
from backend.chargement.lecture_docling import _nettoyer
from backend.chargement.lecture_excel import lire_referentiel
from backend.chargement.lecture_html import lire_faq_html
from backend.chargement.schemas import ChunkLu


## VERSION ##

@pytest.mark.parametrize("texte, attendu", [
    ("Réf. document : MAN-WX-500-FR - Édition 2024 - www.electrodomus.fr", "2024"),
    ("Conditions Générales de Vente (édition janvier 2026)", "janvier 2026"),
    ("Réf. : BT-2026-007 — diffusé le 16 février 2026", "16 février 2026"),
    ("Page mise à jour le 12 janvier 2026 — Service client", "12 janvier 2026"),
    ("Procédure SAV sans date", None),
])
def test_version_extraite_du_document(texte, attendu) :
    assert _extraire_version(texte) == attendu


## MODÈLES ET GAMMES DU DOCUMENT ##

def test_manuel_rattache_a_son_modele() :
    assert _modeles_du_document("Manuel d'utilisation — Lave-linge WX-500", "Manuel_WX-500", []) == ({"WX-500"}, set())


def test_faq_rattachee_a_la_gamme_par_le_type_d_appareil() :
    assert _modeles_du_document("Questions fréquentes — Lave-linge", "faq-lave-linge", []) == (set(), {"WX"})


def test_document_general_sans_modele() :
    assert _modeles_du_document("Conditions Générales de Vente", "CGV_Electrodomus", []) == (set(), set())


def test_rubrique_modeles_concernes_prioritaire_et_parentheses_ignorees() :
    chunks = [ChunkLu(texte="FR-700, FR-750, FR-800 (les FR-600 et FR-650 ne sont pas équipés).", titres=["Modèles concernés"])]
    modeles, gammes = _modeles_du_document("Accompagner un cycle de pyrolyse — gamme FR", "PROC-FR-01_Pyrolyse", chunks)
    assert modeles == {"FR-700", "FR-750", "FR-800"}          # pas les FR-600 / FR-650 exclus, ni toute la gamme FR
    assert gammes == set()


## CONSTRUCTION D'UN CHUNK ##

def test_chunk_porte_son_contexte_et_ses_metadonnees() :
    lu = ChunkLu(texte="Le code E23 du LV-200 signale une sonde défectueuse.", titres=["10. Codes erreur"], pages=[6, 7])
    chunk = _construire_chunk(3, lu, "[Manuel] Manuel — Lave-vaisselle LV-200", {"LV-200"}, set())
    assert chunk.contenu.splitlines()[:2] == ["[Manuel] Manuel — Lave-vaisselle LV-200", "10. Codes erreur"]
    assert chunk.texte == lu.texte and chunk.pages == [6, 7] and chunk.position == 3
    assert chunk.modeles == ["LV-200"] and chunk.codes_erreur == ["E23"]


def test_modele_cite_n_est_pas_pris_pour_une_gamme() :
    lu = ChunkLu(texte="Les modèles WX-400 et WX-450 sont équipés du moteur à induction.")
    chunk = _construire_chunk(0, lu, "[Garantie] Fiche", set(), set())
    assert chunk.modeles == ["WX-400", "WX-450"]
    assert chunk.gammes == []                                  # "modèles WX-400" ne doit pas donner la gamme WX entière


## FAQ HTML ##

FAQ = """<html><body><main>
<h1>Questions fréquentes — Lave-linge</h1>
<div class="updated">Page mise à jour le 12 janvier 2026</div>
<section><h2>Entretien</h2>
<details><summary>Puis-je détartrer avec du vinaigre ?</summary><div><p>Non, utilisez le DT-200.</p></div></details>
<details><summary>Où est le filtre ?</summary><div><p>En bas à droite.</p><p>Derrière la trappe.</p></div></details>
</section></main></body></html>"""


def test_faq_une_question_par_chunk(tmp_path) :
    fichier = tmp_path / "faq.html"
    fichier.write_text(FAQ, encoding="utf-8")
    lu = lire_faq_html(fichier)
    assert lu.titre == "Questions fréquentes — Lave-linge"
    assert "12 janvier 2026" in lu.entete
    assert [chunk.texte for chunk in lu.chunks] == [
        "Question : Puis-je détartrer avec du vinaigre ?\nRéponse : Non, utilisez le DT-200.",
        "Question : Où est le filtre ?\nRéponse : En bas à droite.\nDerrière la trappe.",
    ]
    assert all(chunk.titres == ["Entretien"] for chunk in lu.chunks)


def test_html_sans_structure_faq_ne_donne_aucun_chunk(tmp_path) :
    fichier = tmp_path / "page.html"
    fichier.write_text("<html><body><h1>Page</h1><p>Texte libre.</p></body></html>", encoding="utf-8")
    assert lire_faq_html(fichier).chunks == []                 # data.py passe alors la main a Docling


## RÉFÉRENTIEL EXCEL ##

def test_referentiel_lu_onglet_par_onglet(tmp_path) :
    classeur = openpyxl.Workbook()
    feuille = classeur.active
    feuille.title = "Gamme WX"
    feuille.append(["Référentiel des codes erreur — Lave-linge serie WX"])
    feuille.append(["Version 2025-T4 (arrêtée au 15 décembre 2025)"])
    feuille.append([])
    feuille.append(["Code", "Signification", "Conduite à tenir (client)", "Intervention SAV (technicien)", "Modèles concernés"])
    feuille.append(["E23", "Défaut de la pompe", "Nettoyer le filtre", "Tester la pompe", "WX-300, WX-500"])
    feuille.append(["E31", "Balourd", "Répartir le linge", "Capteur à contrôler", "WX-500"])
    fichier = tmp_path / "referentiel.xlsx"
    classeur.save(fichier)

    referentiel = lire_referentiel(fichier, source="referentiel.xlsx")
    assert referentiel.version == "2025-T4"
    assert [erreur.code for erreur in referentiel.erreurs] == ["E23", "E31"]
    premiere = referentiel.erreurs[0]
    assert (premiere.gamme, premiere.type_appareil, premiere.modeles) == ("WX", "Lave-linge", ["WX-300", "WX-500"])
    assert premiere.intervention == "Tester la pompe"


## NETTOYAGE DU TEXTE CONVERTI ##

def test_nettoyage_des_marques_et_caracteres_parasites() :
    assert _nettoyer("**Important** et *note*") == "Important et note"
    assert _nettoyer("- \uf0b7 Branchez l'appareil") == "- Branchez l'appareil"          # puce de police Symbol (pdf)
    assert _nettoyer("relancer le programme.. E10") == "relancer le programme. E10"     # point de cellule + point ajouté
    assert _nettoyer("ligne   avec    espaces\n\n\nsuite") == "ligne avec espaces\nsuite"
