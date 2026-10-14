"""essai de l'assistant dans le terminal, sans interface ni compte (historique en mémoire, rien n'est enregistré).
lancement depuis la racine du projet : python -m backend.rag.terminal
"""
import logging

from backend.database.db import SessionLocal
from backend.config import CONTACT_SAV
from backend.rag.assistant import pour_historique, preparer, references_citees, separer_contact_sav
from backend.rag.llm import ErreurLLM, FluxLLM
from backend.rag.prompts import formater_pages

COMMANDES_SORTIE = {"q", "quit", "exit", "quitter"}


def converser() -> None :
    historique : list[dict[str, str]] = []
    print("Assistant SAV Electrodomus — posez votre question (q pour quitter)")
    while True :
        try :
            question = input("\nVous : ").strip()
        except (EOFError, KeyboardInterrupt) :
            break
        if not question :
            continue
        if question.lower() in COMMANDES_SORTIE :
            break

        with SessionLocal() as session :
            preparation = preparer(session, question, historique)
        print("\nAssistant : ", end="", flush=True)
        if preparation.messages is None :
            texte, sources = preparation.reponse_directe, []
            print(texte)
        else :
            morceaux = []
            try :
                for morceau in FluxLLM(preparation.messages) :
                    print(morceau, end="", flush=True)
                    morceaux.append(morceau)
            except ErreurLLM as erreur :
                print(f"\n[erreur] {erreur}")
                continue
            texte, contact_sav = separer_contact_sav("".join(morceaux))
            sources = references_citees(texte, preparation.references)
            if contact_sav :
                print(f"\n\nContacter le SAV : {CONTACT_SAV['telephone']} ({CONTACT_SAV['mention']}), {CONTACT_SAV['horaires']}")
            if sources :
                print("\n\nSources :")
                for source in sources :
                    print(f"  [{source.numero}] {source.titre} ({source.source}{formater_pages(source.pages)})")
        historique += [{"role": "user", "content": question}, {"role": "assistant", "content": pour_historique(texte, [source.titre for source in sources])}]


if __name__ == "__main__" :
    from logger import configurer_logs

    configurer_logs(niveau_console=logging.WARNING)     # les logs vont dans logs/briefrag.log, pas au milieu de la conversation
    converser()
