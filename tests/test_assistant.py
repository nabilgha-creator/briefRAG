"""prompts, citations, droits de lecture et titres de conversation (sans base ni LLM)"""
from backend.auth.droits import categories_autorisees, peut_lire
from backend.database.crud_conversations import titre_depuis_question
from backend.database.models import Role, Utilisateur
from backend.rag.assistant import pour_historique, references_citees, separer_contact_sav
from backend.rag.prompts import PROMPT_SYSTEME, construire_messages, formater_pages, message_avec_contexte
from backend.rag.recherche import Appareils, Contexte, Extrait, FicheErreur, Reference


def _contexte(fiches=None, extraits=None) -> Contexte :
    return Contexte(appareils=Appareils(modele="WX-500", type_appareil="Lave-linge", modeles=["WX-500"]), codes=["E23"],
                    fiches=fiches or [], extraits=extraits or [])


## CITATIONS ##

def test_seules_les_sources_citees_sont_retenues() :
    references = [Reference(n, f"titre {n}", f"source {n}") for n in range(1, 6)]
    citees = references_citees("Voir [2][3], puis [1, 4]. Pas [9].", references)
    assert [reference.numero for reference in citees] == [1, 2, 3, 4]


## PROMPT ##

def test_message_contient_appareil_sources_numerotees_et_question() :
    contexte = _contexte(
        fiches=[FicheErreur(1, "E23", "Défaut pompe", "Nettoyer le filtre", "Tester la pompe", ["WX-500"])],
        extraits=[Extrait(2, "Manuel WX-500", "Manuels/Manuel_WX-500.pdf", [8, 9], "[Manuel] WX-500\nTexte du manuel", 0.4)],
    )
    message = message_avec_contexte("Que faire pour E23 ?", contexte)
    assert message.startswith("Appareil : WX-500 (Lave-linge)")
    assert "[1] Fiche erreur E23 (WX-500) : Défaut pompe" in message
    assert "[2] (Manuels/Manuel_WX-500.pdf, p. 8-9)" in message
    assert message.endswith("Question : Que faire pour E23 ?")


def test_message_sans_source_le_signale() :
    assert "aucune source pertinente trouvée" in message_avec_contexte("Question ?", _contexte())


def test_messages_envoyes_au_llm() :
    historique = [{"role": "user", "content": "avant"}, {"role": "assistant", "content": "réponse"}]
    messages = construire_messages("Nouvelle question ?", historique, _contexte())
    assert messages[0] == {"role": "system", "content": PROMPT_SYSTEME}
    assert messages[1:3] == historique                                # l'historique ne contient pas d'anciens extraits
    assert messages[-1]["role"] == "user" and messages[-1]["content"].endswith("Nouvelle question ?")


def test_pages_lisibles() :
    assert (formater_pages([]), formater_pages([8]), formater_pages([8, 9])) == ("", ", p. 8", ", p. 8-9")


## DROITS DE LECTURE ##

def test_administrateur_voit_toutes_les_categories() :
    assert categories_autorisees(Utilisateur(role="admin", rel_role=[])) is None


def test_conseiller_voit_l_union_des_categories_de_ses_roles() :
    roles = [Role(nom="A", categories=["FAQ", "Manuel"]), Role(nom="B", categories=["Manuel", "Garantie"])]
    assert categories_autorisees(Utilisateur(role="conseiller", rel_role=roles)) == ["FAQ", "Garantie", "Manuel"]


def test_conseiller_sans_role_ne_voit_rien() :
    assert categories_autorisees(Utilisateur(role="conseiller", rel_role=[])) == []


def test_peut_lire_selon_les_roles() :
    conseiller = Utilisateur(role="conseiller", rel_role=[Role(nom="A", categories=["FAQ"])])
    assert peut_lire(conseiller, "FAQ") and not peut_lire(conseiller, "Manuel")
    assert peut_lire(Utilisateur(role="admin", rel_role=[]), "Manuel")


## TITRE DE CONVERSATION ##

def test_titre_tire_de_la_premiere_question() :
    assert titre_depuis_question("  Mon WX-500   affiche E52  ") == "Mon WX-500 affiche E52"
    titre = titre_depuis_question("mot " * 50)
    assert len(titre) <= 80 and titre.endswith("…")


def test_historique_sans_numeros_de_citation() :
    """les sources des tours précédents ne sont plus jointes : un [2] resté dans l'historique faisait douter le LLM"""
    assert pour_historique("La porte reste verrouillée 30 à 45 min [2]. Voir [1][3].") == "La porte reste verrouillée 30 à 45 min. Voir."


def test_marqueur_sav_retire_et_signale() :
    assert separer_contact_sav("Planifier un technicien [1].\n[SAV]") == ("Planifier un technicien [1].", True)
    assert separer_contact_sav("Nettoyer le filtre [2].") == ("Nettoyer le filtre [2].", False)
