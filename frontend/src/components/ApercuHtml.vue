<script setup>
// aperçu HTML (docx, xlsx, html) nettoyé par DOMPurify ; passage surligné, question de FAQ dépliée
import DOMPurify from 'dompurify'
import { computed, nextTick, onMounted, ref } from 'vue'

import { localiserPassage } from '@/utils/surlignage'

const props = defineProps({
  html: { type: String, required: true },
  passage: { type: String, default: '' },
})
const emit = defineEmits(['localise'])           // { trouve }

const BLOCS = 'h1, h2, h3, h4, h5, h6, p, li, summary, td, th, caption, dt, dd'
const conteneur = ref(null)
const propre = computed(() => DOMPurify.sanitize(props.html, { FORBID_TAGS: ['style', 'form', 'input', 'button'] }))
let premier = null

/** les blocs de texte, dans l'ordre ; un bloc qui en contient d'autres (<li> avec un <p>) n'est pas compté */
function blocs() {
  return [...conteneur.value.querySelectorAll(BLOCS)].filter((bloc) => !bloc.querySelector(BLOCS))
}

function allerAuPassage(comportement = 'smooth') {
  if (!premier) return
  const boite = conteneur.value.getBoundingClientRect()
  const cible = premier.getBoundingClientRect()
  conteneur.value.scrollTo({ top: conteneur.value.scrollTop + cible.top - boite.top - boite.height / 3, behavior: comportement })
}

onMounted(async () => {
  await nextTick()
  for (const lien of conteneur.value.querySelectorAll('a[href]')) {
    Object.assign(lien, { target: '_blank', rel: 'noopener noreferrer' })     // un lien du document ne quitte pas l'application
  }
  const liste = blocs()
  const indices = localiserPassage(liste.map((bloc) => bloc.textContent), props.passage)
  for (const index of indices) {
    const bloc = liste[index]
    bloc.classList.add('surligne')
    bloc.closest('details')?.setAttribute('open', '')
    bloc.closest('tr')?.classList.add('ligne-surlignee')
  }
  premier = indices.length ? (liste[indices[0]].closest('tr') ?? liste[indices[0]]) : null
  allerAuPassage('auto')
  emit('localise', { trouve: indices.length > 0 })
})

defineExpose({ allerAuPassage })
</script>

<template>
  <div ref="conteneur" class="apercu-html">
    <article class="feuille t" v-html="propre"></article>
  </div>
</template>

<style scoped>
.apercu-html {
  height: 100%;
  overflow: auto;
  padding: 24px 20px;
}

.feuille {
  max-width: 820px;
  margin: 0 auto;
  padding: 36px 44px;
  border: 1px solid var(--bordure);
  border-radius: 14px;
  background-color: var(--carte);
  color: var(--texte2);
  font-size: 15px;
  line-height: 1.65;
  overflow-wrap: anywhere;
}

.feuille :deep(h1) {
  margin: 0 0 14px;
  font-size: 24px;
  line-height: 1.25;
  color: var(--texte);
}

.feuille :deep(h2) {
  margin: 26px 0 10px;
  font-size: 18px;
  color: var(--texte);
}

.feuille :deep(h3),
.feuille :deep(h4) {
  margin: 20px 0 8px;
  font-size: 16px;
  color: var(--texte);
}

.feuille :deep(p) {
  margin: 0 0 10px;
}

.feuille :deep(ul),
.feuille :deep(ol) {
  margin: 0 0 12px;
  padding-left: 24px;
}

.feuille :deep(li) {
  margin-bottom: 4px;
}

.feuille :deep(.updated) {
  margin-bottom: 18px;
  font-size: 13px;
  color: var(--discret);
}

.feuille :deep(details) {
  margin-bottom: 8px;
  padding: 10px 14px;
  border: 1px solid var(--bordure);
  border-radius: 10px;
}

.feuille :deep(summary) {
  font-weight: 600;
  color: var(--texte);
  cursor: pointer;
}

.feuille :deep(details[open] summary) {
  margin-bottom: 8px;
}

.feuille :deep(table) {
  width: 100%;
  margin: 8px 0 22px;
  border-collapse: collapse;
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: normal;          /* un code "E23" ne se coupe pas lettre par lettre dans une colonne étroite */
}

.feuille :deep(th),
.feuille :deep(td) {
  padding: 8px 10px;
  border: 1px solid var(--bordure);
  text-align: left;
  vertical-align: top;
}

.feuille :deep(th) {
  background-color: var(--eleve);
  color: var(--texte);
}

.feuille :deep(.ligne-surlignee td) {
  background-color: var(--surlignage-ligne);
}

.feuille :deep(.surligne) {
  background-color: var(--surlignage);
  border-radius: 4px;
  box-shadow: 0 0 0 3px var(--surlignage);
}

.feuille :deep(td.surligne),
.feuille :deep(th.surligne) {
  border-radius: 0;
  box-shadow: none;
}

@media (max-width: 767px) {
  .apercu-html {
    padding: 12px 8px;
  }

  .feuille {
    padding: 22px 18px;
  }

  /* tableau plus large que l'écran (référentiel : 5 colonnes) : il défile seul, horizontalement */
  .feuille :deep(table) {
    display: block;
    overflow-x: auto;
  }
}
</style>
