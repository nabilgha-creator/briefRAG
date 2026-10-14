# BriefRAG — assistant SAV Electrodomus

Chatbot interne pour les conseillers du service après-vente : il répond aux questions sur les lave-linge (WX),
lave-vaisselle (LV) et fours (FR) **à partir de la documentation Electrodomus** (manuels, procédures SAV,
bulletins techniques, garanties, FAQ, référentiel des codes erreur) et cite ses sources.

- **RAG** : recherche hybride (vecteurs bge-m3 + pgvector pour le sens, BM25 pour les termes exacts : références de pièces,
  bulletins, procédures) et fiches erreur exactes, réponse rédigée par un LLM via OpenRouter
- **Réponses en streaming**, sources numérotées avec extrait, fichier et pages
- **Lecteur de documents** : un clic sur une source ouvre le document (manuel PDF, procédure, FAQ, référentiel)
  au passage cité, surligné ; les droits de lecture des rôles s'appliquent aussi aux fichiers
- **Conversations enregistrées**, comptes utilisateurs, administration et journal des connexions
- **Front Vue.js** animé, thème sombre / clair

## Architecture

```
backend/
├── config.py          chemins et modèle d'embedding
├── ingestion.py       documentation -> base (python -m backend.ingestion)
├── chargement/        lecture et découpage des documents (pdf, docx, html, xlsx), sans base
├── database/          connexion, tables SQLAlchemy, accès aux données (CRUD)
├── rag/               vecteurs, recherche du contexte, prompts, LLM, assistant
├── auth/              mots de passe, sessions, création d'administrateur
└── api/               API HTTP FastAPI utilisée par le front
database/migrations/   migrations Alembic (schéma de la base)
frontend/              application Vue 3 + Vite
assets/                documentation source et caches (non versionné)
logger.py              configuration des logs (fichier logs/briefrag.log)
```

## Prérequis

| Outil               | Version                                           |
| ------------------- | ------------------------------------------------- |
| Python              | 3.12 ou plus (développé avec 3.14)              |
| PostgreSQL          | 18, avec l'extension**pgvector** installée |
| Node.js             | 22 ou plus (pour le front)                        |
| Clé API OpenRouter | https://openrouter.ai/keys                        |

La documentation source n'est pas dans le dépôt : placez-la dans `assets/Documentation_Electrodomus/`
(sous-dossiers `Manuels`, `Procedures_SAV`, `Bulletins_techniques`, `Garanties`, `FAQ`, et le fichier
`Referentiel_codes_erreur.xlsx`).

## Installation

Les commandes se lancent **depuis la racine du projet**.

```bash
# environnement Python
python -m venv venv
venv\Scripts\activate            # Windows   (Linux / macOS : source venv/bin/activate)
pip install -r requirements.txt

# front
cd frontend
npm install
cd ..
```

## Configuration

Créez un fichier `.env` à la racine (il n'est jamais versionné) :

```ini
# base de données (obligatoire)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=BriefRAG
DB_USER=postgres
DB_PASSWORD=...

# LLM via OpenRouter (obligatoire)
CLE_OPENR=sk-or-...

# compte administrateur d'amorçage (cf. "Définir le compte administrateur")
ADMIN_IDENTIFIANT=admin
ADMIN_EMPREINTE='scrypt$...'

# facultatif
HF_TOKEN=...                                  # token Hugging Face (téléchargement des modèles)
MODELE_LLM=anthropic/claude-haiku-5.5         # modèle OpenRouter (valeur par défaut)
EFFORT_LLM=low                                # réflexion du modèle avant de répondre : low, medium, high (défaut low)
TEMPERATURE_LLM=                              # seulement pour un modèle qui l'accepte (Haiku 5.5 la refuse)
DB_ECHO=false                                 # true : affiche le SQL exécuté
FRONT_ORIGINES=http://localhost:5173          # origines autorisées par l'API (CORS)
```

## Premier lancement

### 1. Créer la base

Créez une base vide dans PostgreSQL (pgAdmin ou `psql`) :

```sql
CREATE DATABASE "BriefRAG";
```

Puis créez toutes les tables avec les migrations (l'extension `vector` est activée automatiquement) :

```bash
alembic upgrade head
```

### 2. Ingérer la documentation

```bash
python -m backend.ingestion
```

Lit le référentiel des codes erreur puis tous les documents, les découpe, calcule les vecteurs et remplit la base.
Le premier passage prend une dizaine de minutes (conversion des PDF, téléchargement du modèle bge-m3 d'environ 2 Go) ;
les conversions sont ensuite gardées en cache dans `assets/cache_docling/`.

L'ingestion est **incrémentale** : chaque document garde l'empreinte de son fichier, et une nouvelle ingestion ne
retraite que les fichiers nouveaux ou modifiés (les fichiers supprimés disparaissent de la base). Tout est retraité si
le référentiel Excel change, si les règles de découpage changent (`VERSION_DECOUPAGE` dans `backend/chargement/data.py`)
ou avec `python -m backend.ingestion --tout`.

### 3. Définir le compte administrateur

Le premier compte est défini dans le `.env` par l'**empreinte** de son mot de passe (jamais le mot de passe en clair).
Générez-la :

```bash
python -m backend.auth.empreinte
```

puis copiez les lignes affichées dans le `.env` (gardez les guillemets simples) :

```ini
ADMIN_IDENTIFIANT=admin
ADMIN_EMPREINTE='scrypt$16384$8$1$...$...'
ADMIN_NOM=Administrateur          # facultatif
```

Au démarrage de l'API, si aucun administrateur actif n'existe, ce compte est créé : connectez-vous avec cet
identifiant et le mot de passe choisi. Dès qu'un administrateur actif existe, le `.env` ne modifie plus rien ;
si plus aucun administrateur n'est actif (compte désactivé, mot de passe perdu…), redémarrer l'API rétablit l'accès.

Les autres comptes se créent ensuite depuis la page **Administration** de l'application
(ou en ligne de commande : `python -m backend.auth.creer_admin`).

## Lancer l'application

Deux terminaux, depuis la racine du projet :

```bash
# terminal 1 : l'API (http://localhost:8000, documentation des routes sur http://localhost:8000/docs)
uvicorn backend.api.app:app --reload

# terminal 2 : le front (http://localhost:5173)
cd frontend
npm run dev
```

Ouvrez http://localhost:5173 et connectez-vous. En développement, le front appelle l'API via `/api`
(redirigé par Vite vers le port 8000).

## Comptes et droits d'accès

Chaque compte a :

- un **type de compte** : *administrateur* (gère les comptes et les rôles, voit toute la documentation) ou *conseiller* ;
- un ou plusieurs **rôles d'accès**, qui définissent les **catégories de documents** consultables :
  Manuel, Procédure SAV, Bulletin technique, Garantie, FAQ, Référentiel codes erreur.

Un conseiller voit les catégories de tous ses rôles. Le filtre s'applique à la recherche, côté serveur : l'assistant
ne reçoit et ne cite jamais un document que l'utilisateur n'a pas le droit de consulter (les fiches erreur exactes
suivent la catégorie « Référentiel codes erreur »). Un conseiller sans rôle n'a accès à aucun document.

Les rôles se gèrent dans **Administration › Rôles d'accès** ; on les attribue en créant ou modifiant un compte.
Un rôle de départ « Accès complet » (toutes les catégories) est créé par les migrations.

## Tests

```bash
pytest                       # tous les tests (≈ 30 s)
pytest -m "not integration"  # tests unitaires seuls : ni base, ni réseau (≈ 15 s)
```

- **Tests unitaires** : sécurité, chargement (versions, modèles, FAQ, Excel, nettoyage), analyse des questions,
  prompts, citations, droits de lecture.
- **Tests d'intégration** (`-m integration`) : recherche sur la vraie base et API de bout en bout. Ils créent des
  comptes `test_…` et des rôles `Test …`, supprimés à la fin, et sont sautés si la base est injoignable.
  Le LLM est remplacé par une réponse fixe : aucun appel à OpenRouter, aucun coût.

## Évaluation de la recherche

```bash
python -m backend.evaluation.recall                             # réglages actuels
python -m backend.evaluation.recall --seuil 0.6 --extraits 6    # comparer d'autres réglages, sans modifier le code
python -m backend.evaluation.recall --sans-lexicale             # recherche par vecteurs seule
```

Lance la vraie recherche du chatbot sur un jeu de 33 questions de référence (`backend/evaluation/questions_recall.json`,
avec pour chacune les documents qui contiennent la réponse) et mesure, sans appeler le LLM :

- le **rappel** : part des documents attendus qui sont bien envoyés au LLM (1 = rien ne manque) ;
- la **précision** : part des extraits envoyés qui sont utiles ;
- le **MRR** : un document utile arrive-t-il en tête ?
- les **fiches erreur** exactes fournies.

Pour chaque document manquant, le rapport dit pourquoi (seuil de distance, classement, dédoublonnage, filtre des
modèles). Les résultats sont enregistrés en CSV dans `assets/evaluation/` (ouverture directe dans Excel) :
`recall_<date>.csv` (une ligne par question) et `historique_recall.csv` (une ligne par mesure, pour suivre l'évolution).

## Commandes utiles

| Commande                                             | Rôle                                                                                                                                        |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `python -m backend.rag.terminal`                   | essayer l'assistant dans le terminal, sans le front                                                                                          |
| `python -m backend.chargement.data`                | découper la documentation sans toucher à la base ; résultat dans`assets/chunks.json`                                                    |
| `python -m backend.ingestion`                      | réingérer après un ajout ou une modification de document : seuls les fichiers nouveaux ou modifiés sont retraités (`--tout` pour tout refaire) |
| `alembic revision --autogenerate -m "description"` | créer une migration après une modification de`backend/database/models.py`                                                                |
| `alembic upgrade head`                             | appliquer les migrations en attente                                                                                                          |
| `alembic check`                                    | vérifier que la base correspond aux modèles                                                                                                |
| `alembic upgrade head --sql`                       | afficher le SQL complet du schéma                                                                                                           |
| `cd frontend && npm run build`                     | construire le front pour la production (dossier`frontend/dist/`)                                                                           |

Les logs détaillés sont dans `logs/briefrag.log`.

## Coût

Avec `anthropic/claude-haiku-5.5` (0,10 $ en entrée / 0,50 $ en sortie par million de tokens, pour un prompt de moins
de 100 000 tokens), une question coûte environ 0,04 à 0,08 centime, réflexion du modèle comprise (contre 0,3 centime
avec Claude Haiku 4.5). Le coût et les tokens de chaque réponse sont enregistrés dans la table `message`.
