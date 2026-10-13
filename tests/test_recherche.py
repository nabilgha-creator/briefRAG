"""analyse de la question (appareils, codes) et construction du contexte, sans base de données"""
from types import SimpleNamespace

import pytest

from backend.database.models import Modele
from backend.rag.recherche import (Appareils, Contexte, Extrait, FicheErreur, _apercu, _fiches, analyser_appareils,
                                   extraire_codes)


@pytest.fixture
def modeles() -> list[Modele] :
    return [Modele(modele="WX-300", type="Lave-linge"), Modele(modele="WX-500", type="Lave-linge"),
            Modele(modele="LV-200", type="Lave-vaisselle"),
            Modele(modele="FR-600", type="Fours encastrables"), Modele(modele="FR-700", type="Fours encastrables")]


## APPAREILS ##

def test_un_modele_cite(modeles) :
    appareils = analyser_appareils(["Mon WX-500 affiche E23"], modeles)
    assert (appareils.modele, appareils.type_appareil, appareils.modeles) == ("WX-500", "Lave-linge", ["WX-500"])


@pytest.mark.parametrize("ecriture", ["wx500", "WX 500", "wx-500"])
def test_ecritures_libres_du_modele(modeles, ecriture) :
    assert analyser_appareils([f"le client a un {ecriture}"], modeles).modele == "WX-500"


def test_type_seul_couvre_toute_la_gamme(modeles) :
    appareils = analyser_appareils(["mon lave-linge fuit"], modeles)
    assert appareils.modele is None
    assert appareils.modeles == ["WX-300", "WX-500"]


def test_plusieurs_types_cites_couvrent_les_deux_gammes(modeles) :
    """non-régression : seule la 1re gamme trouvée était retenue, les lave-linge étaient exclus de la recherche"""
    appareils = analyser_appareils(["codes erreur fréquents sur les lave-linge et fours"], modeles)
    assert set(appareils.modeles) == {"WX-300", "WX-500", "FR-600", "FR-700"}
    assert "LV-200" not in appareils.modeles
    assert "Lave-linge" in appareils.type_appareil and "Fours encastrables" in appareils.type_appareil


def test_type_et_modele_du_meme_type_ne_retient_que_le_modele(modeles) :
    assert analyser_appareils(["mon lave-linge WX-500 vibre"], modeles).modeles == ["WX-500"]


def test_plusieurs_modeles_cites(modeles) :
    appareils = analyser_appareils(["E23 sur LV-200 et sur WX-500 ?"], modeles)
    assert set(appareils.modeles) == {"LV-200", "WX-500"} and appareils.modele is None
    assert set(appareils.modeles_cites) == {"LV-200", "WX-500"}


def test_appareil_repris_de_la_conversation(modeles) :
    # textes du plus récent au plus ancien : la question courte ne cite rien, la précédente cite le LV-200
    assert analyser_appareils(["et que faire ?", "Mon LV-200 affiche E15"], modeles).modele == "LV-200"


def test_aucun_appareil(modeles) :
    assert analyser_appareils(["Comment enregistrer mon produit ?"], modeles) == Appareils()


## CODES ERREUR ##

def test_codes_erreur_normalises_et_dedoublonnes() :
    assert extraire_codes("e23 puis E 52, encore E23") == ["E23", "E52"]
    assert extraire_codes("pièce 44-3311, version 2025") == []


def test_fiches_regroupent_les_modeles_de_meme_definition() :
    erreurs = [SimpleNamespace(modele=modele, signification=sens, conduite="c", intervention="i")
               for modele, sens in [("WX-300", "Pompe"), ("WX-500", "Pompe"), ("LV-200", "Sonde")]]
    fiches = _fiches(erreurs, "E23", premier_numero=1)
    assert [(fiche.numero, fiche.signification, fiche.modeles) for fiche in fiches] == [
        (1, "Pompe", ["WX-300", "WX-500"]), (2, "Sonde", ["LV-200"])]


## CONTEXTE ##

def test_code_sans_appareil_demande_le_modele() :
    assert Contexte(appareils=Appareils(), codes=["E23"], fiches=[], extraits=[]).besoin_precision
    assert not Contexte(appareils=Appareils(modeles=["WX-500"]), codes=["E23"], fiches=[], extraits=[]).besoin_precision
    assert not Contexte(appareils=Appareils(), codes=[], fiches=[], extraits=[]).besoin_precision


def test_references_numerotees_fiches_puis_extraits() :
    contexte = Contexte(
        appareils=Appareils(modele="WX-500", modeles=["WX-500"]), codes=["E52"],
        fiches=[FicheErreur(1, "E52", "Sonde", "Contacter le SAV", "Remplacer la sonde", ["WX-500"])],
        extraits=[Extrait(2, "Bulletin BT-2026-007", "Bulletins_techniques/BT-2026-007.docx", [], "[Bulletin] BT\nTexte", 0.4)],
    )
    fiche, extrait = contexte.references()
    assert (fiche.numero, fiche.source, fiche.distance) == (1, "table erreur", None)       # donnée exacte
    assert (extrait.numero, extrait.distance, extrait.extrait) == (2, 0.4, "Texte")


def test_apercu_sans_ligne_de_contexte_et_tronque() :
    assert _apercu("[Manuel] Titre du document\nPremière phrase. Seconde phrase.") == "Première phrase. Seconde phrase."
    long = _apercu("[x] titre\n" + "mot " * 200)
    assert len(long) <= 221 and long.endswith("…")
