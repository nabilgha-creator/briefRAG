/**
 * retrouve un passage (le texte d'un chunk) parmi les blocs d'un document affiché : lignes de texte d'un pdf,
 * paragraphes, éléments de liste ou cellules d'un aperçu HTML.
 *
 * le texte du chunk n'est pas identique au document : tableaux réécrits une ligne par ligne
 * ("E01, Signification = Porte mal verrouillée"), espaces normalisés, titres de section ajoutés en tête.
 * on cherche donc les blocs dont le texte est CONTENU dans le passage, puis on garde la suite de blocs la plus
 * fournie : une correspondance isolée ailleurs dans le document ("Codes erreur" dans un sommaire) est ignorée.
 */
const RE_PRIVES = /[-]/g      // puces des polices Symbol des pdf, retirées aussi du texte des chunks
const RE_CODE = /^[a-z]\d{2}$/            // code erreur seul dans une cellule : "e23"
const LONGUEUR_MIN = 4                    // en dessous, un bloc ("le", "de") se retrouverait partout
const TROU_MAX = 2                        // blocs non retrouvés tolérés au milieu du passage (mot coupé en fin de ligne...)
const DEBUT_PASSAGE = 60                  // un bloc plus long que le passage doit en contenir le début

export function normaliser(texte) {
  return (texte ?? '')
    .normalize('NFKC')
    .replace(RE_PRIVES, '')
    .replace(/[’‘]/g, "'")
    .replace(/\*\*/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim()
}

function correspond(bloc, passage, debut) {
  if (bloc.length >= LONGUEUR_MIN && passage.includes(bloc)) return true
  if (RE_CODE.test(bloc)) return new RegExp(`\\b${bloc}\\b`).test(passage)
  return debut.length >= 30 && bloc.includes(debut)      // passage plus court que le bloc (simple début d'extrait)
}

/**
 * textes : le texte de chaque bloc, dans l'ordre du document.
 * renvoie les indices des blocs du passage, du premier au dernier (vide si le passage est introuvable)
 */
export function localiserPassage(textes, passage) {
  const cible = normaliser(passage).replace(/…$/, '').trim()      // "…" : début d'extrait tronqué (repli)
  if (!cible) return []
  const debut = cible.slice(0, DEBUT_PASSAGE)

  let meilleure = { indices: [], score: 0 }
  let courante = { indices: [], score: 0 }
  let trou = 0
  const clore = () => {
    if (courante.score > meilleure.score) meilleure = courante
    courante = { indices: [], score: 0 }
    trou = 0
  }

  textes.forEach((texte, index) => {
    const bloc = normaliser(texte)
    if (!bloc) return                                       // bloc vide (espace d'un pdf) : neutre
    if (correspond(bloc, cible, debut)) {
      courante.indices.push(index)
      courante.score += Math.min(bloc.length, cible.length)
      trou = 0
    } else if (courante.indices.length && ++trou > TROU_MAX) {
      clore()
    }
  })
  clore()

  if (!meilleure.indices.length) return []
  // les blocs non retrouvés pris entre deux blocs du passage en font partie (ligne coupée, cellule réécrite)
  const [premier, dernier] = [meilleure.indices[0], meilleure.indices.at(-1)]
  const indices = []
  for (let index = premier; index <= dernier; index++) if (normaliser(textes[index])) indices.push(index)
  return indices
}
