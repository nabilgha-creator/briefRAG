"""fixtures. tests "integration" : base du .env (sautés si injoignable), comptes test_ et rôles "Test " nettoyés,
LLM remplacé par faux_llm (aucun appel)"""
import pytest
from sqlalchemy import delete, text

MOT_DE_PASSE = "motdepasse-test"


## BASE DE DONNÉES ##

@pytest.fixture(scope="session")
def base_disponible() -> None :
    try :
        from backend.database.db import engine
        with engine.connect() as connexion :
            connexion.execute(text("select 1"))
    except Exception as erreur :
        pytest.skip(f"base PostgreSQL injoignable : {erreur}")


def _nettoyer() -> None :
    from backend.database.db import SessionLocal
    from backend.database.models import Connexion, Role, Utilisateur
    with SessionLocal.begin() as session :
        session.execute(delete(Utilisateur).where(Utilisateur.identifiant.startswith("test_", autoescape=True)))
        session.execute(delete(Connexion).where(Connexion.identifiant.startswith("test_", autoescape=True)))
        session.execute(delete(Role).where(Role.nom.startswith("Test ")))


@pytest.fixture
def nettoyage(base_disponible) :
    _nettoyer()
    yield
    _nettoyer()


@pytest.fixture
def session_bd(base_disponible) :
    """session en lecture ; tout ce qui y est écrit est annulé a la fin"""
    from backend.database.db import SessionLocal
    with SessionLocal() as session :
        yield session
        session.rollback()


## API ##

@pytest.fixture(scope="session")
def client(base_disponible) :
    """client de test de l'API (démarre l'application : charge bge-m3, environ 10 s la première fois)"""
    from fastapi.testclient import TestClient
    from backend.api.app import app
    with TestClient(app) as client_test :
        yield client_test


@pytest.fixture
def creer_compte(nettoyage) :
    """crée un compte de test ; renvoie son identifiant"""
    from backend.database.crud_utilisateurs import creer_utilisateur
    from backend.database.db import SessionLocal

    def creer(identifiant : str, role : str = "conseiller", ids_roles : list[int] | None = None) -> str :
        assert identifiant.startswith("test_")
        with SessionLocal.begin() as session :
            creer_utilisateur(session, identifiant, f"Compte {identifiant}", MOT_DE_PASSE, role, ids_roles)
        return identifiant
    return creer


@pytest.fixture
def creer_role(nettoyage) :
    """crée un rôle de test ; renvoie son identifiant"""
    from backend.database.crud_roles import creer_role as creer_role_bd
    from backend.database.db import SessionLocal

    def creer(nom : str, categories : list[str]) -> int :
        assert nom.startswith("Test ")
        with SessionLocal.begin() as session :
            return creer_role_bd(session, nom, categories).id_role
    return creer


@pytest.fixture
def connecter(client) :
    """se connecte et renvoie l'en-tête d'authentification"""
    def connecter(identifiant : str) -> dict[str, str] :
        reponse = client.post("/auth/connexion", json={"identifiant": identifiant, "mot_de_passe": MOT_DE_PASSE})
        assert reponse.status_code == 200, reponse.text
        return {"Authorization": f"Bearer {reponse.json()['jeton']}"}
    return connecter


## LLM ##

REPONSE_FAUSSE = ["Réponse ", "de test ", "[1]."]


@pytest.fixture
def faux_llm(monkeypatch) -> str :
    """remplace l'appel a OpenRouter (streaming et réponse complète) par une réponse fixe"""
    from backend.rag.llm import Consommation, ReponseLLM

    class FauxFlux :
        def __init__(self, messages : list[dict]) -> None :
            self.messages = messages
            self.consommation = Consommation(modele="faux-modele", tokens_entree=10, tokens_sortie=3, cout=0.0)

        def __iter__(self) :
            yield from REPONSE_FAUSSE

    monkeypatch.setattr("backend.api.routes_conversations.FluxLLM", FauxFlux)
    monkeypatch.setattr("backend.rag.assistant.completer",
                        lambda messages : ReponseLLM("".join(REPONSE_FAUSSE), Consommation("faux-modele", 10, 3, 0.0)))
    return "".join(REPONSE_FAUSSE)
