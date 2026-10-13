"""structures de données du chargement des documents.

- ChunkLu / DocumentLu : ce que renvoient les lecteurs (lecture_docling, lecture_html), sans métadonnées métier
- ChunkCharge / DocumentCharge : le résultat final de data.py, prêt pour l'ingestion en base
- ErreurReferentiel / Referentiel : le référentiel excel des codes erreur (lecture_excel)

aucune dépendance a la base de données ni a LangChain.
"""
from dataclasses import dataclass, field


@dataclass
class ChunkLu :
    """un morceau de texte découpé par un lecteur"""
    texte : str
    titres : list[str] = field(default_factory=list)      # chemin des titres de section, ex : ["2. Installation", "2.3 Raccordement en eau"]
    pages : list[int] = field(default_factory=list)       # vide pour les formats sans pages (docx, html)


@dataclass
class DocumentLu :
    """un document lu et découpé, avant enrichissement"""
    titre : str | None          # titre trouvé dans le document, None si introuvable
    entete : str                # texte du début du document, sert a retrouver la version / date
    chunks : list[ChunkLu]


@dataclass
class ChunkCharge :
    """un chunk final : contenu contextualisé (a vectoriser et a stocker) + métadonnées"""
    position : int
    contenu : str               # [type] titre du document + titres de section + texte
    texte : str                 # texte seul, sans contexte
    titres : list[str]
    pages : list[int]
    modeles : list[str]         # modèles cités explicitement, ex : ["WX-500"]
    gammes : list[str]          # gammes concernées entièrement, ex : ["LV"] (a résoudre en modèles a l'ingestion)
    codes_erreur : list[str]    # ex : ["E15", "E20"]


@dataclass
class ErreurReferentiel :
    """une ligne du référentiel : un code erreur d'une gamme et les modèles qu'il concerne"""
    gamme : str                 # WX
    type_appareil : str         # Lave-linge
    code : str                  # E23
    signification : str
    conduite : str              # conduite a tenir (client)
    intervention : str          # intervention SAV (technicien)
    modeles : list[str]


@dataclass
class Referentiel :
    source : str
    version : str | None
    erreurs : list[ErreurReferentiel]


@dataclass
class DocumentCharge :
    source : str                # chemin relatif au dossier de documentation, identifiant stable du fichier
    type_document : str         # Manuel, Procédure SAV, Bulletin technique, Garantie, FAQ
    titre : str
    version : str | None
    modeles : list[str]
    gammes : list[str]
    chunks : list[ChunkCharge]
