"""textes envoyés au LLM. économie de tokens : les extraits accompagnent seulement la question en cours,
jamais l'historique"""
from backend.rag.recherche import Contexte, Extrait, FicheErreur

PROMPT_SYSTEME = """Tu es l'assistant interne des conseillers du service après-vente Electrodomus (lave-linge WX, lave-vaisselle LV, fours FR).

Règles :
- Réponds uniquement à partir des fiches erreur et des extraits fournis avec la question. Si l'information n'y est pas, dis-le et indique ce qu'il faudrait préciser. N'invente jamais un code, une référence de pièce, une durée ou une condition de garantie.
- Les sources des échanges précédents ne sont plus jointes : ne remets pas en cause tes réponses précédentes faute de les revoir.
- Un code erreur n'a pas le même sens selon l'appareil : précise toujours le modèle ou la gamme concernés. Ne redemande le modèle que si la réponse en dépend (si la fiche est la même pour tous les modèles de la gamme, réponds directement).
- En cas de contradiction : un bulletin technique prévaut sur le référentiel des codes erreur, qui prévaut sur les manuels. Signale la contradiction.
- Distingue ce que le client peut faire lui-même de ce qui demande un technicien.
- Cite tes sources par leur numéro entre crochets, par exemple [1] ou [2][3].
- Réponds en français, de façon concise et structurée (étapes numérotées pour une procédure), sans emoji.
- Si ta réponse oriente vers un technicien ou le service après-vente, ou si l'information manque dans les sources, termine par une dernière ligne contenant seulement [SAV]."""

MARQUEUR_SAV = "[SAV]"         # retiré de la réponse par assistant.py : il affiche le bouton « Contacter le SAV »

MESSAGE_PRECISION_MODELE = ("La signification de ce code erreur dépend de l'appareil. Pouvez-vous préciser le modèle "
                            "(par exemple WX-500, LV-200 ou FR-700, indiqué sur l'étiquette signalétique) ?")


def formater_pages(pages : list[int]) -> str :
    if not pages :
        return ""
    return f", p. {pages[0]}" if len(pages) == 1 else f", p. {pages[0]}-{pages[-1]}"


def _fiche(fiche : FicheErreur) -> str :
    return (f"[{fiche.numero}] Fiche erreur {fiche.code} ({', '.join(fiche.modeles)}) : {fiche.signification}\n"
            f"Conduite à tenir (client) : {fiche.conduite}\n"
            f"Intervention SAV (technicien) : {fiche.intervention}")


def _extrait(extrait : Extrait) -> str :
    # le contenu commence déjà par "[type] titre du document" : l'en-tête ne répète que la source et les pages
    return f"[{extrait.numero}] ({extrait.source}{formater_pages(extrait.pages)})\n{extrait.contenu}"


def _appareil(contexte : Contexte) -> str :
    appareils = contexte.appareils
    if appareils.modele :
        return f"Appareil : {appareils.modele} ({appareils.type_appareil})"
    if appareils.type_appareil :
        precision = f"modèles cités : {', '.join(appareils.modeles_cites)}" if appareils.modeles_cites else "modèle non précisé"
        return f"Appareils : {appareils.type_appareil}, {precision}"
    return "Appareil : non précisé"


def message_avec_contexte(question : str, contexte : Contexte) -> str :
    """le message utilisateur envoyé au LLM : appareil, sources numérotées, puis la question"""
    parties = [_appareil(contexte)]
    sources = [_fiche(fiche) for fiche in contexte.fiches] + [_extrait(extrait) for extrait in contexte.extraits]
    parties.append("<sources>\n" + "\n\n".join(sources) + "\n</sources>" if sources else "<sources>aucune source pertinente trouvée</sources>")
    parties.append(f"Question : {question}")
    return "\n\n".join(parties)


def construire_messages(question : str, historique : list[dict[str, str]], contexte : Contexte) -> list[dict[str, str]] :
    """historique : messages précédents {"role", "content"} déjà réduits aux derniers échanges"""
    return ([{"role": "system", "content": PROMPT_SYSTEME}] + historique
            + [{"role": "user", "content": message_avec_contexte(question, contexte)}])
