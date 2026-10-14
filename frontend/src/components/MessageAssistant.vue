<script setup>
// streaming : paragraphes terminés en markdown, paragraphe en cours mot a mot en fondu ; a la fin tout en markdown
import { computed, ref } from 'vue'

import EtapesRecherche from './EtapesRecherche.vue'
import Icone from './Icone.vue'
import { apiSav } from '@/api/routes'
import { markdownEnHtml, sansMarqueurSav, texteSansMarques } from '@/utils/format'

const props = defineProps({
  message: { type: Object, required: true },
  phase: { type: String, default: null },               // étape en cours si la réponse n'a pas commencé
  sourceActive: { type: Number, default: null },
  selectionne: { type: Boolean, default: false },       // ce message alimente le panneau des sources
})
const emit = defineEmits(['choisir-source'])

const enAttente = computed(() => props.message.enCours && !props.message.contenu)

const contenu = computed(() => sansMarqueurSav(props.message.contenu, props.message.enCours))

const decoupage = computed(() => {
  if (!props.message.enCours) return { termine: contenu.value, courant: '' }
  const blocs = contenu.value.split(/\n{2,}/)
  return { termine: blocs.slice(0, -1).join('\n\n'), courant: blocs.at(-1) }
})

const html = computed(() => {
  const rendu = markdownEnHtml(decoupage.value.termine)
  if (!props.selectionne || props.sourceActive === null) return rendu
  return rendu.replaceAll(`class="cite" data-source="${props.sourceActive}"`, `class="cite active" data-source="${props.sourceActive}"`)
})

// mots du paragraphe en cours, espaces et retours a la ligne compris (clé = position : seuls les nouveaux mots s'animent)
const motsCourants = computed(() => texteSansMarques(decoupage.value.courant).match(/\S+\s*/g) ?? [])

function clic(evenement) {
  const bouton = evenement.target.closest('.cite')
  if (bouton) emit('choisir-source', Number(bouton.dataset.source))
}

async function copier(texte = contenu.value) {
  try {
    await navigator.clipboard.writeText(texte)
    return true
  } catch {
    return false          // presse-papiers indisponible (contexte non sécurisé)
  }
}

// bouton « Contacter le SAV » : réponse qui oriente vers le SAV (marqueur [SAV] du LLM)
const contactOuvert = ref(false)
const contact = ref(null)
const numeroCopie = ref(false)

async function basculerContact() {
  contactOuvert.value = !contactOuvert.value
  if (!contactOuvert.value || contact.value?.telephone) return
  try {
    contact.value = await apiSav.contact()
  } catch {
    contact.value = { erreur: true }
  }
}

async function copierNumero() {
  numeroCopie.value = await copier(contact.value.telephone)
  setTimeout(() => { numeroCopie.value = false }, 1500)
}
</script>

<template>
  <article class="assistant" :aria-busy="message.enCours">
    <EtapesRecherche v-if="enAttente" :phase="phase ?? 'analyse'" />

    <div v-else class="corps" @click="clic">
      <div class="markdown" v-html="html"></div>
      <p v-if="motsCourants.length" class="courant"><span v-for="(mot, index) in motsCourants" :key="index" class="fondu-mot">{{ mot }}</span></p>
    </div>

    <p v-if="message.erreur" class="erreur" role="alert">
      <Icone nom="alerte" />
      <span>{{ message.erreur }}</span>
    </p>

    <div v-if="!message.enCours && message.contenu" class="outils apparition">
      <button type="button" class="bouton-icone petit" aria-label="Copier la réponse" @click="copier">
        <Icone nom="copier" :taille="16" />
      </button>
      <span v-if="message.sources?.length" class="mono compte">{{ message.sources.length }} source{{ message.sources.length > 1 ? 's' : '' }} citée{{ message.sources.length > 1 ? 's' : '' }}</span>
      <button v-if="message.contact_sav" type="button" class="bouton-sav" :aria-expanded="contactOuvert" @click="basculerContact">
        <Icone nom="telephone" :taille="15" />
        Contacter le SAV
      </button>
    </div>

    <div v-if="contactOuvert" class="contact-sav apparition" role="region" aria-label="Coordonnées du SAV client">
      <template v-if="contact?.telephone">
        <span class="mono numero">{{ contact.telephone }}</span>
        <span class="details">{{ contact.mention }} · {{ contact.horaires }}</span>
        <button type="button" class="bouton-icone petit" :aria-label="numeroCopie ? 'Numéro copié' : 'Copier le numéro'" @click="copierNumero">
          <Icone :nom="numeroCopie ? 'coche' : 'copier'" :taille="15" />
        </button>
      </template>
      <span v-else-if="contact?.erreur" class="details">Coordonnées indisponibles pour le moment.</span>
      <span v-else class="details">Chargement…</span>
    </div>
  </article>
</template>

<style scoped>
.assistant {
  max-width: 720px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 15px;
  line-height: 1.65;
  color: var(--texte2);
}

.courant {
  margin: 0;
  white-space: pre-wrap;
}

.erreur {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  padding: 10px 14px;
  border-radius: 12px;
  background-color: var(--erreur-fond);
  color: var(--erreur);
  font-size: 14px;
  font-weight: 600;
}

.outils {
  display: flex;
  align-items: center;
  gap: 8px;
}

.petit {
  width: 36px;
  height: 36px;
}

.compte {
  font-size: 11px;
  color: var(--discret);
}

.bouton-sav {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  margin-left: auto;
  padding: 0 12px;
  border: 1.5px solid var(--acc2);
  border-radius: 999px;
  background-color: var(--acc-fond2);
  color: var(--acc-texte);
  font-size: 13px;
  font-weight: 700;
  transition: background-color 0.2s;
}

.bouton-sav:hover {
  background-color: var(--acc-fond);
}

.contact-sav {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 14px;
  padding: 10px 10px 10px 16px;
  border: 1px solid var(--bordure);
  border-radius: 12px;
  background-color: var(--acc-fond2);
}

.numero {
  font-size: 17px;
  font-weight: 600;
  color: var(--texte);
}

.details {
  flex: 1;
  font-size: 13px;
  color: var(--doux);
}

/* mise en forme du markdown rendu (v-html : styles en :deep) */
.markdown :deep(h1),
.markdown :deep(h2),
.markdown :deep(h3) {
  margin: 14px 0 6px;
  color: var(--texte);
  font-weight: 700;
  line-height: 1.3;
}

.markdown :deep(h1) { font-size: 19px; }
.markdown :deep(h2) { font-size: 17px; }
.markdown :deep(h3) { font-size: 15px; color: var(--acc-texte); }

.markdown :deep(> :first-child) {
  margin-top: 0;
}

.markdown :deep(p) {
  margin: 0 0 10px;
}

.markdown :deep(ul),
.markdown :deep(ol) {
  margin: 0 0 10px;
  padding-left: 22px;
}

.markdown :deep(li) {
  margin: 3px 0;
}

.markdown :deep(li::marker) {
  color: var(--acc-texte);
}

.markdown :deep(strong) {
  color: var(--texte);
}

.markdown :deep(hr) {
  border: 0;
  border-top: 1px solid var(--bordure);
  margin: 14px 0;
}

.markdown :deep(code) {
  padding: 1px 6px;
  border-radius: 6px;
  background-color: var(--eleve);
  font-family: var(--police-mono);
  font-size: 13px;
}

.markdown :deep(table) {
  border-collapse: collapse;
  margin: 0 0 10px;
  font-size: 14px;
}

.markdown :deep(th),
.markdown :deep(td) {
  padding: 6px 10px;
  border: 1px solid var(--bordure);
  text-align: left;
}
</style>
