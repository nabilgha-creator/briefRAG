"""requêtes envoyées au LLM et lecture de ses réponses, sans réseau"""
import json

import pytest

from backend.rag import llm


def _ligne(donnees : dict) -> str :
    return "data: " + json.dumps(donnees)


class _ReponseFactice :
    """réponse en streaming d'OpenRouter, sans réseau"""
    status_code = 200

    def __init__(self, lignes : list[str]) -> None :
        self.lignes = lignes

    def iter_lines(self) :
        return iter(self.lignes)

    def __enter__(self) :
        return self

    def __exit__(self, *exception) :
        return False


def test_corps_sans_temperature_avec_effort(monkeypatch) :
    for variable in ("TEMPERATURE_LLM", "EFFORT_LLM", "MODELE_LLM") :
        monkeypatch.delenv(variable, raising=False)
    corps = llm._corps([{"role": "user", "content": "question"}], flux=True)
    assert corps["model"] == "anthropic/claude-haiku-5.5"
    assert "temperature" not in corps                     # Claude Haiku 5.5 la refuse (erreur 400)
    assert corps["reasoning"] == {"effort": "low"} and corps["max_tokens"] == llm.MAX_TOKENS_REPONSE


def test_temperature_et_effort_reglables(monkeypatch) :
    monkeypatch.setenv("TEMPERATURE_LLM", "0.2")
    monkeypatch.setenv("EFFORT_LLM", "medium")
    corps = llm._corps([], flux=False)
    assert corps["temperature"] == 0.2 and corps["reasoning"] == {"effort": "medium"}


def test_la_reflexion_est_ignoree_seul_le_texte_est_lu(monkeypatch) :
    monkeypatch.setenv("CLE_OPENR", "cle-de-test")
    lignes = [_ligne({"choices": [{"delta": {"reasoning": "je réfléchis"}}]}),
              _ligne({"choices": [{"delta": {"content": "Bonjour"}, "finish_reason": "stop"}]}),
              "data: [DONE]"]
    monkeypatch.setattr(llm.httpx, "stream", lambda *arguments, **options : _ReponseFactice(lignes))
    assert list(llm.FluxLLM([{"role": "user", "content": "question"}])) == ["Bonjour"]


def test_reponse_sans_texte_signalee(monkeypatch) :
    """la réflexion a épuisé le plafond (ou le modèle refuse) : une erreur lisible plutôt qu'une réponse vide enregistrée"""
    monkeypatch.setenv("CLE_OPENR", "cle-de-test")
    lignes = [_ligne({"choices": [{"delta": {"reasoning": "…"}, "finish_reason": "length"}]}), "data: [DONE]"]
    monkeypatch.setattr(llm.httpx, "stream", lambda *arguments, **options : _ReponseFactice(lignes))
    with pytest.raises(llm.ErreurLLM, match="length") :
        list(llm.FluxLLM([{"role": "user", "content": "question"}]))
