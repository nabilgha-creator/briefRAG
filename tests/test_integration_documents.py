"""lecteur de documents de bout en bout : fichier, aperçu, passage, droits des rôles et sécurité des chemins"""
import pytest
from sqlalchemy import select

from backend.database.models import Chunk, Document

pytestmark = pytest.mark.integration

MANUEL = "Manuels/Manuel_WX-500.pdf"
FAQ = "FAQ/faq-fours.html"
REFERENTIEL = "Referentiel_codes_erreur.xlsx"


@pytest.fixture
def conseiller_faq(client, creer_compte, creer_role, connecter) -> dict[str, str] :
    """en-tête d'un conseiller qui ne lit que la FAQ"""
    creer_compte("test_faq", ids_roles=[creer_role("Test FAQ", ["FAQ"])])
    return connecter("test_faq")


@pytest.fixture
def admin(client, creer_compte, connecter) -> dict[str, str] :
    creer_compte("test_admin", role="admin")
    return connecter("test_admin")


def _id_chunk(session_bd, source : str) -> int :
    return session_bd.scalars(select(Chunk.id_chunk).join(Document).where(Document.source == source).limit(1)).one()


def test_pdf_servi_tel_quel(client, admin) :
    reponse = client.get("/documents/fichier", params={"source": MANUEL}, headers=admin)
    assert reponse.status_code == 200 and reponse.headers["content-type"] == "application/pdf"
    assert reponse.content.startswith(b"%PDF") and reponse.headers["content-disposition"].startswith("inline")


def test_telechargement_en_piece_jointe(client, admin) :
    reponse = client.get("/documents/fichier", params={"source": FAQ, "telechargement": True}, headers=admin)
    assert reponse.headers["content-disposition"].startswith("attachment")


def test_apercu_du_referentiel(client, admin) :
    apercu = client.get("/documents/apercu", params={"source": REFERENTIEL}, headers=admin).json()
    assert "<td>E52</td>" in apercu["html"] and apercu["categorie"] == "Référentiel codes erreur"


def test_pas_d_apercu_html_pour_un_pdf(client, admin) :
    assert client.get("/documents/apercu", params={"source": MANUEL}, headers=admin).status_code == 400


def test_droits_des_roles_appliques(client, conseiller_faq, session_bd) :
    assert client.get("/documents/apercu", params={"source": FAQ}, headers=conseiller_faq).status_code == 200
    assert client.get("/documents/fichier", params={"source": MANUEL}, headers=conseiller_faq).status_code == 403
    assert client.get(f"/documents/passages/{_id_chunk(session_bd, MANUEL)}", headers=conseiller_faq).status_code == 403


@pytest.mark.parametrize("source", ["../.env", "..\\.env", "Manuels/../../.env", "Manuels/inexistant.pdf"])
def test_seules_les_sources_en_base_sont_servies(client, admin, source) :
    assert client.get("/documents/fichier", params={"source": source}, headers=admin).status_code == 404


def test_passage_sans_sa_ligne_de_contexte(client, admin, session_bd) :
    id_chunk = _id_chunk(session_bd, MANUEL)
    passage = client.get(f"/documents/passages/{id_chunk}", headers=admin).json()
    contenu = session_bd.get(Chunk, id_chunk).contenu
    assert passage["source"] == MANUEL and passage["texte"] == contenu.split("\n", 1)[1]
    assert not passage["texte"].startswith("[Manuel]")


def test_passage_inconnu(client, admin) :
    assert client.get("/documents/passages/999999999", headers=admin).status_code == 404


def test_sans_connexion(client) :
    assert client.get("/documents/fichier", params={"source": MANUEL}).status_code == 401


def test_les_sources_d_une_reponse_disent_quoi_ouvrir(client, creer_compte, creer_role, connecter, faux_llm) :
    toutes = ["Manuel", "Procédure SAV", "Bulletin technique", "Garantie", "FAQ", "Référentiel codes erreur"]
    creer_compte("test_conseiller", ids_roles=[creer_role("Test complet", toutes)])
    entete = connecter("test_conseiller")
    conversation = client.post("/conversations", headers=entete, json={}).json()
    reponse = client.post(f"/conversations/{conversation['id_conversation']}/messages", headers=entete,
                          json={"question": "Mon WX-500 affiche E52, que faire ?"}).json()
    fiche = reponse["sources"][0]                     # [1] = la fiche erreur E52 du WX-500
    assert fiche["source"] == "table erreur" and fiche["document"] == REFERENTIEL and fiche["id_chunk"] is None
