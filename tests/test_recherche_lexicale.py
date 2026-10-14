"""recherche lexicale (BM25) et fusion des classements, sans base"""
from types import SimpleNamespace

import pytest

from backend.rag.recherche import _fusionner
from backend.rag.recherche_lexicale import IndexLexical, ResultatLexical, decouper


## DÉCOUPAGE ET MOTIFS ##

@pytest.mark.parametrize("texte, terme", [
    ("pièce 44-3311", "44-3311"),
    ("Que dit le BT-2026-011 ?", "bt-2026-011"),
    ("la procédure PROC-WX-03", "proc-wx-03"),
    ("code E 23", "e23"),
    ("PROC-WX-03_Nettoyage_filtre_vidange.docx", "proc-wx-03"),       # nom de fichier : "_" séparateur
])
def test_references_reconnues_et_normalisees(texte, terme) :
    termes = decouper(texte)
    assert terme in termes.tous and terme in termes.references


@pytest.mark.parametrize("ecriture", ["WX-500", "wx500", "WX 500"])
def test_modele_reconnu_mais_pas_compte_comme_reference(ecriture) :
    termes = decouper(f"mon {ecriture}")
    assert "wx-500" in termes.tous and not termes.references          # les modèles servent déjà de filtre


def test_mots_vides_et_racines() :
    assert decouper("Comment nettoyer les filtres bouchés ?").tous == decouper("nettoyer filtre bouché").tous    # mots vides, pluriels
    assert decouper("n'évacue plus").tous[-1] == decouper("évacuation").tous[0] == "evacu"                  # racine Snowball
    assert "44" not in decouper("pièce 44-3311").tous                 # les morceaux d'une référence ne comptent pas en plus


## BM25 ##

@pytest.fixture
def index() -> IndexLexical :
    return IndexLexical([
        (1, "Nettoyer le filtre de vidange du lave-linge"),
        (2, "Programmes du lave-linge : coton, synthétique"),
        (3, "Contrôler le relais K2 avant de remplacer la résistance de sole (pièce 62-1340)"),
        (4, "Lave-linge : brides de transport, lave-linge neuf, lave-linge qui vibre, lave-linge bruyant"),
        (5, "Consignes de sécurité générales"),
    ])


def test_terme_rare_compte_plus_qu_un_terme_present_partout() :
    # "lave-linge" dans 10 chunks sur 11, "relais" dans un seul : comme dans la vraie documentation
    index = IndexLexical([(numero, f"lave-linge, programme {numero}") for numero in range(1, 11)] + [(11, "relais de la carte")])
    assert index.idf(decouper("relais").tous[0]) > index.idf("lav")
    assert index.scores("relais du lave-linge")[0].id_chunk == 11


def test_repeter_un_terme_aide_de_moins_en_moins(index) :
    index.part_discriminante = 1.0                     # tous les termes comptent (sinon "lave-linge" est trop courant)
    scores = {resultat.id_chunk : resultat.score for resultat in index.scores("lave-linge")}
    assert scores[4] > scores[2]                       # 4 occurrences contre 1...
    assert scores[4] < 4 * scores[2]                   # ... mais pas 4 fois plus (saturation)


def test_reference_comptee_double_et_signalee(index) :
    resultat = index.scores("la pièce 62-1340")[0]
    assert resultat.id_chunk == 3 and resultat.references == ["62-1340"]


def test_chunks_autorises_seulement_et_aucun_terme_commun(index) :
    index.part_discriminante = 1.0
    assert [resultat.id_chunk for resultat in index.scores("lave-linge", autorises={2, 5})] == [2]
    assert index.scores("pyrolyse") == []


def test_que_des_mots_courants_aucun_resultat(index) :
    """non-régression : "lave-linge" (dans 3 chunks sur 5) ramenait des chunks quelconques, qui évinçaient les bons"""
    assert index.scores("lave-linge") == []
    assert [resultat.id_chunk for resultat in index.scores("filtre du lave-linge")] == [1]      # "filtre" est discriminant


def test_le_modele_ne_compte_pas_dans_la_requete() :
    """le modèle est déjà un filtre : compté, il favorisait tous les chunks de son manuel"""
    index = IndexLexical([(1, "Manuel WX-300 : consignes WX-300"), (2, "Procédure : évacuation de l'eau")])
    assert [resultat.id_chunk for resultat in index.scores("mon WX-300 n'évacue plus")] == [2]


## FUSION DES CLASSEMENTS ##

def test_un_chunk_classe_par_les_deux_recherches_passe_devant() :
    chunk = lambda identifiant : SimpleNamespace(id_chunk=identifiant)
    vectoriels = [(chunk(1), 0.3), (chunk(2), 0.35), (chunk(3), 0.4)]
    lexicaux = [ResultatLexical(3, 12.0, []), ResultatLexical(4, 9.0, [])]
    ordre = _fusionner(vectoriels, lexicaux)
    assert ordre[0] == 3                               # 3e par vecteurs et 1er par termes
    assert set(ordre) == {1, 2, 3, 4}                  # le chunk trouvé par les termes seuls entre dans la course


## INDEX EN MÉMOIRE ##

def test_index_reconstruit_apres_une_ingestion(monkeypatch) :
    import backend.rag.recherche_lexicale as module
    versions = iter([(2, 10), (2, 10), (3, 12)])                  # (nombre de chunks, plus grand identifiant)
    textes = [(1, "filtre"), (2, "joint")]
    monkeypatch.setattr(module, "_index", None)
    monkeypatch.setattr(module, "version_des_chunks", lambda session : next(versions))
    monkeypatch.setattr(module, "textes_des_chunks", lambda session : [(identifiant, texte, "source") for identifiant, texte in textes])
    premier = module.index_lexical(None)
    assert module.index_lexical(None) is premier                 # rien n'a changé en base : même index
    textes.append((3, "pompe"))
    nouveau = module.index_lexical(None)                          # nouvelle version : index reconstruit
    assert nouveau is not premier and 3 in nouveau.longueurs
