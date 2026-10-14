"""API de bout en bout : connexion, comptes, rôles, conversations. le LLM est remplacé (fixture faux_llm)"""
import json

import pytest

pytestmark = pytest.mark.integration

TOUTES_CATEGORIES = ["Manuel", "Procédure SAV", "Bulletin technique", "Garantie", "FAQ", "Référentiel codes erreur"]


def _evenements(texte_sse : str) -> list[tuple[str, dict]] :
    """découpe un flux server-sent events en (nom, données)"""
    evenements = []
    for bloc in filter(None, texte_sse.split("\n\n")) :
        lignes = dict(ligne.split(": ", 1) for ligne in bloc.splitlines())
        evenements.append((lignes["event"], json.loads(lignes["data"])))
    return evenements


## CONNEXION ##

def test_connexion_refusee_puis_journalisee(client, creer_compte, connecter) :
    creer_compte("test_admin", role="admin")
    refus = client.post("/auth/connexion", json={"identifiant": "test_admin", "mot_de_passe": "mauvais-mot-de-passe"})
    assert refus.status_code == 401 and refus.json()["detail"] == "identifiant ou mot de passe incorrect"
    admin = connecter("test_admin")
    journal = client.get("/utilisateurs/connexions", headers=admin, params={"limite": 5}).json()
    assert [(entree["identifiant"], entree["succes"]) for entree in journal[:2]] == [("test_admin", True), ("test_admin", False)]


def test_route_protegee_sans_jeton(client) :
    assert client.get("/conversations").status_code == 401


def test_deconnexion_invalide_le_jeton(client, creer_compte, connecter) :
    creer_compte("test_conseiller")
    entete = connecter("test_conseiller")
    assert client.post("/auth/deconnexion", headers=entete).status_code == 204
    assert client.get("/auth/moi", headers=entete).status_code == 401


## COMPTES ET RÔLES ##

def test_admin_cree_un_role_puis_un_compte_avec_ce_role(client, creer_compte, connecter) :
    creer_compte("test_admin", role="admin")
    admin = connecter("test_admin")
    role = client.post("/roles", headers=admin, json={"nom": "Test FAQ", "categories": ["FAQ"]})
    assert role.status_code == 201
    compte = client.post("/utilisateurs", headers=admin, json={
        "identifiant": "test_nouveau", "nom": "Nouveau", "mot_de_passe": "motdepasse-1", "roles": [role.json()["id_role"]]})
    assert compte.status_code == 201 and [r["nom"] for r in compte.json()["roles"]] == ["Test FAQ"]
    assert client.post("/roles", headers=admin, json={"nom": "test faq", "categories": []}).status_code == 409      # casse ignorée
    assert client.post("/roles", headers=admin, json={"nom": "Test x", "categories": ["Inconnue"]}).status_code == 422


def test_conseiller_ne_peut_pas_administrer(client, creer_compte, connecter) :
    creer_compte("test_conseiller")
    entete = connecter("test_conseiller")
    assert client.get("/utilisateurs", headers=entete).status_code == 403
    assert client.get("/roles", headers=entete).status_code == 403


def test_dernier_admin_actif_protege(client, creer_compte, connecter, monkeypatch) :
    creer_compte("test_admin", role="admin")
    admin = connecter("test_admin")
    monkeypatch.setattr("backend.api.routes_utilisateurs.compter_admins_actifs", lambda session : 1)   # comme s'il était seul
    id_admin = client.get("/auth/moi", headers=admin).json()["id_utilisateur"]
    assert client.patch(f"/utilisateurs/{id_admin}", headers=admin, json={"actif": False}).status_code == 409
    assert client.delete(f"/utilisateurs/{id_admin}", headers=admin).status_code == 409


## CONVERSATIONS ##

def test_question_en_streaming_enregistree(client, creer_compte, creer_role, connecter, faux_llm) :
    creer_compte("test_conseiller", ids_roles=[creer_role("Test complet", TOUTES_CATEGORIES)])
    entete = connecter("test_conseiller")
    conversation = client.post("/conversations", headers=entete, json={}).json()
    reponse = client.post(f"/conversations/{conversation['id_conversation']}/messages/flux", headers=entete,
                          json={"question": "Mon WX-500 affiche E52, que faire ?"})
    evenements = _evenements(reponse.text)
    assert "".join(donnees["texte"] for nom, donnees in evenements if nom == "morceau") == faux_llm
    nom_fin, fin = evenements[-1]
    assert nom_fin == "fin" and fin["consommation"]["modele"] == "faux-modele"
    assert [source["numero"] for source in fin["sources"]] == [1]           # seule la source citée [1] est gardée

    detail = client.get(f"/conversations/{conversation['id_conversation']}", headers=entete).json()
    assert detail["titre"] == "Mon WX-500 affiche E52, que faire ?"
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]


def test_question_en_json(client, creer_compte, creer_role, connecter, faux_llm) :
    creer_compte("test_conseiller", ids_roles=[creer_role("Test complet", TOUTES_CATEGORIES)])
    entete = connecter("test_conseiller")
    conversation = client.post("/conversations", headers=entete, json={}).json()
    reponse = client.post(f"/conversations/{conversation['id_conversation']}/messages", headers=entete,
                          json={"question": "Comment nettoyer le filtre du WX-300 ?"})
    assert reponse.status_code == 200 and reponse.json()["reponse"] == faux_llm


def test_code_sans_modele_repondu_sans_llm(client, creer_compte, connecter, faux_llm) :
    creer_compte("test_conseiller")
    entete = connecter("test_conseiller")
    conversation = client.post("/conversations", headers=entete, json={}).json()
    reponse = client.post(f"/conversations/{conversation['id_conversation']}/messages", headers=entete,
                          json={"question": "Que veut dire le code E23 ?"}).json()
    assert "préciser le modèle" in reponse["reponse"] and reponse["consommation"] is None


def test_conversation_d_un_autre_utilisateur_invisible(client, creer_compte, connecter) :
    creer_compte("test_a")
    creer_compte("test_b")
    conversation = client.post("/conversations", headers=connecter("test_a"), json={}).json()
    assert client.get(f"/conversations/{conversation['id_conversation']}", headers=connecter("test_b")).status_code == 404


def test_question_trop_longue_refusee(client, creer_compte, connecter) :
    creer_compte("test_conseiller")
    entete = connecter("test_conseiller")
    conversation = client.post("/conversations", headers=entete, json={}).json()
    reponse = client.post(f"/conversations/{conversation['id_conversation']}/messages", headers=entete, json={"question": "x" * 2001})
    assert reponse.status_code == 422


## CONTACT SAV ##

def test_reponse_orientant_vers_le_sav(client, creer_compte, creer_role, connecter, monkeypatch) :
    """le marqueur [SAV] du LLM (même découpé dans le flux) est retiré du texte et enregistré avec le message"""
    from backend.rag.llm import Consommation

    class FluxSav :
        def __init__(self, messages : list[dict]) -> None :
            self.consommation = Consommation(modele="faux-modele")

        def __iter__(self) :
            yield from ["Planifier un technicien [1].", "\n[S", "AV]"]

    monkeypatch.setattr("backend.api.routes_conversations.FluxLLM", FluxSav)
    creer_compte("test_conseiller", ids_roles=[creer_role("Test complet", TOUTES_CATEGORIES)])
    entete = connecter("test_conseiller")
    conversation = client.post("/conversations", headers=entete, json={}).json()
    flux = client.post(f"/conversations/{conversation['id_conversation']}/messages/flux", headers=entete,
                       json={"question": "Mon WX-500 affiche E52, que faire ?"})
    assert _evenements(flux.text)[-1][1]["contact_sav"] is True
    reponse = client.get(f"/conversations/{conversation['id_conversation']}", headers=entete).json()["messages"][-1]
    assert reponse["contact_sav"] and reponse["contenu"] == "Planifier un technicien [1]."


def test_coordonnees_du_sav(client, creer_compte, connecter) :
    creer_compte("test_conseiller")
    assert client.get("/sav").status_code == 401
    assert client.get("/sav", headers=connecter("test_conseiller")).json()["telephone"] == "0 970 820 340"
