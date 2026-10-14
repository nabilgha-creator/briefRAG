import DOMPurify from 'dompurify'
import { marked } from 'marked'

marked.setOptions({ gfm: true, breaks: true })

const RE_CITATION = /\[(\d+(?:\s*[,;]\s*\d+)*)\]/g

/** markdown du LLM -> HTML nettoyé (DOMPurify : aucun script ne passe), citations [n] -> boutons */
export function markdownEnHtml(texte) {
  const html = DOMPurify.sanitize(marked.parse(texte ?? ''))
  return html.replace(RE_CITATION, (_, groupe) =>
    groupe
      .split(/[,;]/)
      .map((numero) => numero.trim())
      .map((numero) => `<button type="button" class="cite" data-source="${numero}" aria-label="Voir la source ${numero}">${numero}</button>`)
      .join(''),
  )
}

const RE_SAV = /\s*\[SAV\]/g
const RE_SAV_PARTIEL = /\s*\[(?:S(?:AV?)?)?$/       // début du marqueur arrivé en fin de flux : "[", "[S", "[SA"

/** texte sans le marqueur [SAV] du LLM (le serveur le retire aussi a l'enregistrement) */
export function sansMarqueurSav(texte, enCours = false) {
  const propre = (texte ?? '').replace(RE_SAV, '')
  return enCours ? propre.replace(RE_SAV_PARTIEL, '') : propre
}

/** texte affiché pendant le streaming, avant mise en forme : sans les marques markdown */
export function texteSansMarques(texte) {
  return texte
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*|__|`/g, '')
    .replace(/^\s*[-*]\s+/gm, '• ')
}

const heure = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' })
const jour = new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
const jourCourt = new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: '2-digit' })

function ecartEnJours(date) {
  const debut = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate())
  return Math.round((debut(new Date()) - debut(date)) / 86_400_000)
}

/** "Aujourd'hui, 15:40" / "Hier, 17:05" / "02/10/2026, 09:31" */
export function dateLisible(iso) {
  if (!iso) return 'Jamais'
  const date = new Date(iso)
  const ecart = ecartEnJours(date)
  if (ecart === 0) return `Aujourd'hui, ${heure.format(date)}`
  if (ecart === 1) return `Hier, ${heure.format(date)}`
  return `${jour.format(date)}, ${heure.format(date)}`
}

/** "15:40" / "hier" / "02/10" (liste des conversations) */
export function dateCourte(iso) {
  const date = new Date(iso)
  const ecart = ecartEnJours(date)
  if (ecart === 0) return heure.format(date)
  if (ecart === 1) return 'hier'
  return jourCourt.format(date)
}

/** type affiché d'une source, d'après son chemin */
export function typeSource(source) {
  if (source === 'table erreur') return 'FICHE ERREUR'
  const types = { Manuels: 'MANUEL', Procedures_SAV: 'PROCÉDURE SAV', Bulletins_techniques: 'BULLETIN TECHNIQUE', Garanties: 'GARANTIE', FAQ: 'FAQ' }
  const dossier = source.split('/')[0]
  if (types[dossier]) return types[dossier]
  return source.endsWith('.xlsx') ? 'RÉFÉRENTIEL' : 'DOCUMENT'
}

/** fichier ouvert par le lecteur ; sources anciennes : la source elle-même, null pour une fiche erreur */
export function fichierDeSource(source) {
  return source.document ?? (source.source !== 'table erreur' ? source.source : null)
}

export function pagesLisibles(pages) {
  if (!pages?.length) return ''
  return pages.length === 1 ? `p. ${pages[0]}` : `p. ${pages[0]}-${pages.at(-1)}`
}
