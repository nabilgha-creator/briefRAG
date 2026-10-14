<script setup>
// pdf.js : canvas + couche de texte (spans transparents, servent au surlignage). passage cherché dans le texte
// avant tout dessin ; ses pages d'abord, les autres a l'approche de l'écran
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { GlobalWorkerOptions, TextLayer, getDocument } from 'pdfjs-dist'
import urlTravailleur from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

import { localiserPassage } from '@/utils/surlignage'

GlobalWorkerOptions.workerSrc = urlTravailleur

const props = defineProps({
  donnees: { type: ArrayBuffer, required: true },
  pages: { type: Array, default: () => [] },      // pages du passage (1 = première) ; vide = inconnues
  passage: { type: String, default: '' },
})
const emit = defineEmits(['localise'])           // { trouve, page }

const ECHELLE_MAX = 1.6
const MARGE = 40                                 // px laissés autour des pages
const conteneur = ref(null)
const pagesPdf = []                              // { numero, page, viewport, element, rendu, aSurligner }
let chargement = null
let observateur = null
let annule = false
let premierSurligne = null

/** dessine une page (canvas + couche de texte) une seule fois, puis surligne ses blocs du passage */
function dessiner(info) {
  info.rendu ??= (async () => {
    const { page, viewport, element } = info
    const ratio = window.devicePixelRatio || 1
    const canvas = document.createElement('canvas')
    canvas.width = Math.floor(viewport.width * ratio)
    canvas.height = Math.floor(viewport.height * ratio)
    element.append(canvas)
    await page.render({ canvasContext: canvas.getContext('2d'), viewport, transform: ratio === 1 ? null : [ratio, 0, 0, ratio, 0, 0] }).promise

    const calque = document.createElement('div')
    calque.className = 'textLayer'
    element.append(calque)
    const couche = new TextLayer({ textContentSource: page.streamTextContent(), container: calque, viewport })
    await couche.render()
    for (const index of info.aSurligner) couche.textDivs[index]?.classList.add('surligne')
  })().catch((erreur) => {
    if (!annule) console.error(`page ${info.numero} non affichée`, erreur)
  })
  return info.rendu
}

/** cherche le passage dans le texte des pages candidates ; renvoie les numéros des pages où il se trouve */
async function localiser() {
  const candidates = pagesPdf.filter((info) => props.pages.includes(info.numero))
  const parcourues = candidates.length ? candidates : pagesPdf
  const blocs = []                                // { info, index } : un bloc = un élément de texte d'une page
  for (const info of parcourues) {
    const { items } = await info.page.getTextContent()        // mêmes éléments, dans le même ordre, que la couche de texte
    items.forEach((element, index) => blocs.push({ info, index, texte: element.str }))
  }
  const trouves = localiserPassage(blocs.map((bloc) => bloc.texte), props.passage).map((rang) => blocs[rang])
  for (const { info, index } of trouves) info.aSurligner.push(index)
  return [...new Set(trouves.map((bloc) => bloc.info.numero))]
}

function defilerVers(element, comportement) {
  const boite = conteneur.value.getBoundingClientRect()
  const cible = element.getBoundingClientRect()
  conteneur.value.scrollTo({ top: conteneur.value.scrollTop + cible.top - boite.top - boite.height / 3, behavior: comportement })
}

/** revient au passage (bouton du lecteur), ou a défaut a sa première page */
function allerAuPassage(comportement = 'smooth') {
  const page = pagesPdf.find((info) => info.numero === props.pages[0])?.element
  const cible = premierSurligne ?? page
  if (cible) defilerVers(cible, comportement)
}

onMounted(async () => {
  try {
    // copie : pdf.js transfère les données a son worker
    chargement = getDocument({ data: new Uint8Array(props.donnees.slice(0)) })
    const pdf = await chargement.promise
    const largeurPage = (await pdf.getPage(1)).getViewport({ scale: 1 }).width
    const echelle = Math.min(ECHELLE_MAX, (conteneur.value.clientWidth - MARGE) / largeurPage)

    // des pages vides a la bonne taille d'abord : on peut défiler jusqu'au passage avant que tout soit dessiné
    for (let numero = 1; numero <= pdf.numPages && !annule; numero++) {
      const page = await pdf.getPage(numero)
      const viewport = page.getViewport({ scale: echelle })
      const element = document.createElement('div')
      element.className = 'page-pdf'
      element.dataset.page = numero
      element.setAttribute('aria-label', `Page ${numero}`)
      Object.assign(element.style, { width: `${viewport.width}px`, height: `${viewport.height}px` })
      element.style.setProperty('--scale-factor', echelle)
      conteneur.value.append(element)
      pagesPdf.push({ numero, page, viewport, element, rendu: null, aSurligner: [] })
    }
    if (annule) return

    const pagesDuPassage = await localiser()
    const aDessiner = pagesDuPassage.length ? pagesDuPassage : props.pages.slice(0, 1)
    await Promise.all(pagesPdf.filter((info) => aDessiner.includes(info.numero)).map(dessiner))
    if (annule) return

    premierSurligne = conteneur.value.querySelector('.surligne')
    allerAuPassage('auto')
    emit('localise', { trouve: Boolean(premierSurligne), page: aDessiner[0] ?? 1 })

    observateur = new IntersectionObserver((entrees) => {
      for (const entree of entrees) {
        if (entree.isIntersecting) dessiner(pagesPdf[Number(entree.target.dataset.page) - 1])
      }
    }, { root: conteneur.value, rootMargin: '600px 0px' })
    for (const info of pagesPdf) observateur.observe(info.element)
  } catch (erreur) {
    if (!annule) emit('localise', { trouve: false, page: null, erreur: `document illisible : ${erreur.message}` })
  }
})

onBeforeUnmount(() => {
  annule = true
  observateur?.disconnect()
  chargement?.destroy()
})

defineExpose({ allerAuPassage })
</script>

<template>
  <div ref="conteneur" class="apercu-pdf"></div>
</template>

<style>
/* non scopé : les pages et leur couche de texte sont créées par pdf.js, hors du template.
   règles de la couche de texte reprises de pdfjs-dist/web/pdf_viewer.css (seulement ce qui sert ici) */
.apercu-pdf {
  height: 100%;
  overflow: auto;
  padding: 20px;
}

.apercu-pdf .page-pdf {
  --user-unit: 1;
  --total-scale-factor: calc(var(--scale-factor) * var(--user-unit));
  --scale-round-x: 1px;
  --scale-round-y: 1px;
  position: relative;
  margin: 0 auto 18px;
  background-color: #ffffff;
  border-radius: 4px;
  box-shadow: 0 6px 24px var(--ombre);
  overflow: hidden;
}

.apercu-pdf canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.apercu-pdf .textLayer {
  --min-font-size: 1;
  --text-scale-factor: calc(var(--total-scale-factor) * var(--min-font-size));
  --min-font-size-inv: calc(1 / var(--min-font-size));
  position: absolute;
  inset: 0;
  overflow: clip;
  line-height: 1;
  text-align: initial;
  text-size-adjust: none;
  forced-color-adjust: none;
  transform-origin: 0 0;
  z-index: 0;
}

.apercu-pdf .textLayer :is(span, br) {
  position: absolute;
  color: transparent;
  white-space: pre;
  cursor: text;
  transform-origin: 0% 0%;
}

.apercu-pdf .textLayer > :not(.markedContent),
.apercu-pdf .textLayer .markedContent span:not(.markedContent) {
  --font-height: 0;
  --scale-x: 1;
  --rotate: 0deg;
  z-index: 1;
  font-size: calc(var(--text-scale-factor) * var(--font-height));
  transform: rotate(var(--rotate)) scaleX(var(--scale-x)) scale(var(--min-font-size-inv));
}

.apercu-pdf .textLayer .markedContent {
  display: contents;
}

.apercu-pdf .textLayer ::selection {
  background: rgba(0, 90, 255, 0.25);
  color: transparent;
}

.apercu-pdf .textLayer span.surligne {
  background-color: var(--surlignage);
  border-radius: 3px;
  mix-blend-mode: multiply;
}
</style>
