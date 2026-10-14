<script setup>
/**
 * lecteur de document : ouvre le fichier d'une source et surligne le passage cité.
 * - pdf : affiché tel quel (pdf.js), au passage ;
 * - docx, xlsx, html : aperçu HTML fourni par l'API ; une fiche erreur ouvre le référentiel a la ligne du code.
 * le passage est le texte complet du chunk (GET /documents/passages/{id}) ; a défaut (ancienne conversation,
 * document réingéré depuis), le début d'extrait affiché dans le panneau des sources.
 */
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'

import ApercuHtml from './ApercuHtml.vue'
import Icone from './Icone.vue'
import { apiDocuments } from '@/api/routes'
import { fichierDeSource, pagesLisibles, typeSource } from '@/utils/format'

// pdf.js (≈ 400 Ko) n'est chargé que pour ouvrir un pdf
const ApercuPdf = defineAsyncComponent(() => import('./ApercuPdf.vue'))

const props = defineProps({
  source: { type: Object, required: true },
})
const emit = defineEmits(['fermer'])

const fichier = computed(() => fichierDeSource(props.source))
const estPdf = computed(() => fichier.value?.toLowerCase().endsWith('.pdf') ?? false)

const chargement = ref(true)
const erreur = ref('')
const alerte = ref('')
const donneesPdf = shallowRef(null)
const html = ref('')
const passage = ref({ texte: '', pages: [] })
const localisation = ref(null)                   // { trouve, page }
const apercu = ref(null)
const boutonFermer = ref(null)
let focusPrecedent = null

const emplacement = computed(() => {
  const pages = pagesLisibles(passage.value.pages)
  return pages ? `${fichier.value}, ${pages}` : fichier.value
})

// rien a dire quand le passage est surligné : on ne prévient que s'il n'a pas été retrouvé
const etat = computed(() => {
  if (!localisation.value || localisation.value.trouve) return ''
  const page = localisation.value.page
  return page ? `passage non localisé précisément, ouvert à la page ${page}` : 'passage non localisé précisément'
})

async function chargerPassage() {
  const repli = { texte: props.source.extrait ?? '', pages: props.source.pages ?? [] }
  if (!props.source.id_chunk) return repli
  try {
    const { texte, pages } = await apiDocuments.passage(props.source.id_chunk)
    return { texte, pages }
  } catch (probleme) {
    if (probleme.statut === 404) return repli        // document réingéré depuis la réponse : l'extrait suffit
    throw probleme
  }
}

function localise(resultat) {
  if (resultat.erreur) erreur.value = resultat.erreur
  localisation.value = resultat
}

async function telecharger() {
  alerte.value = ''
  try {
    await apiDocuments.telecharger(fichier.value)
  } catch (probleme) {
    alerte.value = probleme.message
  }
}

function touche(evenement) {
  if (evenement.key === 'Escape') emit('fermer')
}

onMounted(async () => {
  focusPrecedent = document.activeElement
  window.addEventListener('keydown', touche)
  await nextTick()
  boutonFermer.value?.focus()
  if (!fichier.value) {
    erreur.value = 'Cette source ne correspond à aucun document à ouvrir.'
    chargement.value = false
    return
  }
  try {
    const [lu, contenu] = await Promise.all([
      chargerPassage(),
      estPdf.value ? apiDocuments.fichier(fichier.value) : apiDocuments.apercu(fichier.value),
    ])
    passage.value = lu
    if (estPdf.value) donneesPdf.value = contenu
    else html.value = contenu.html
  } catch (probleme) {
    erreur.value = probleme.statut === 403 ? "Vous n'avez pas accès à ce document." : probleme.message
  } finally {
    chargement.value = false
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', touche)
  focusPrecedent?.focus?.()
})
</script>

<template>
  <Teleport to="body">
    <div class="voile" @click.self="emit('fermer')">
      <section class="lecteur t" role="dialog" aria-modal="true" aria-labelledby="titre-lecteur">
        <header class="entete">
          <div class="infos">
            <span class="ligne">
              <span class="pastille">{{ source.numero }}</span>
              <span class="type">{{ typeSource(fichier ?? source.source) }}</span>
              <span v-if="etat" class="mono etat">{{ etat }}</span>
            </span>
            <h2 id="titre-lecteur">{{ source.titre }}</h2>
            <span v-if="fichier" class="mono chemin">{{ emplacement }}</span>
            <span v-if="alerte" class="alerte" role="alert">{{ alerte }}</span>
          </div>
          <div class="actions">
            <button v-if="localisation?.trouve" type="button" class="bouton-secondaire passage" @click="apercu?.allerAuPassage()">
              <Icone nom="cible" :taille="17" />
              <span>Revenir au passage</span>
            </button>
            <button v-if="fichier && !erreur" type="button" class="bouton-icone" aria-label="Télécharger le fichier d'origine"
                    title="Télécharger le fichier d'origine" @click="telecharger">
              <Icone nom="telecharger" />
            </button>
            <button ref="boutonFermer" type="button" class="bouton-icone" aria-label="Fermer le lecteur" title="Fermer (Échap)"
                    @click="emit('fermer')">
              <Icone nom="croix" />
            </button>
          </div>
        </header>

        <div class="corps">
          <div v-if="chargement" class="message">
            <span class="roue anneau" aria-hidden="true"></span>
            <span>Ouverture du document…</span>
          </div>
          <div v-else-if="erreur" class="message probleme" role="alert">
            <Icone nom="alerte" :taille="26" :epaisseur="1.8" />
            <span>{{ erreur }}</span>
          </div>
          <ApercuPdf v-else-if="estPdf" ref="apercu" :donnees="donneesPdf" :pages="passage.pages" :passage="passage.texte"
                     @localise="localise" />
          <ApercuHtml v-else ref="apercu" :html="html" :passage="passage.texte" @localise="localise" />
        </div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.voile {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: 3vh 3vw;
  background-color: var(--voile);
  backdrop-filter: blur(3px);
  animation: apparition-voile 0.25s ease both;
}

.lecteur {
  display: flex;
  flex-direction: column;
  width: min(1080px, 100%);
  height: 100%;
  border: 1px solid var(--bordure2);
  border-radius: 18px;
  background-color: var(--panneau);
  box-shadow: 0 24px 70px var(--ombre);
  overflow: hidden;
  animation: apparition-lecteur 0.3s cubic-bezier(0.2, 0.7, 0.2, 1) both;
}

.entete {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px 16px 14px 22px;
  border-bottom: 1px solid var(--bordure);
}

.infos {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}

.ligne {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.type {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.8px;
  color: var(--doux);
}

.etat {
  font-size: 11px;
  color: var(--discret);
}

h2 {
  margin: 0;
  font-size: 17px;
  line-height: 1.35;
  color: var(--texte);
}

.chemin {
  font-size: 12px;
  color: var(--discret);
  overflow-wrap: anywhere;
}

.alerte {
  font-size: 13px;
  color: var(--erreur);
}

.actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.passage {
  height: 40px;
  margin-right: 6px;
  padding: 0 14px;
  font-size: 13px;
}

.corps {
  flex: 1;
  min-height: 0;
  background-color: var(--fond);
}

.message {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 100%;
  padding: 24px;
  color: var(--doux);
  text-align: center;
}

.probleme {
  color: var(--erreur);
}

.anneau {
  width: 26px;
  height: 26px;
  border: 3px solid var(--bordure2);
  border-top-color: var(--acc1);
  border-radius: 50%;
}

@keyframes apparition-voile {
  from { opacity: 0; }
}

@keyframes apparition-lecteur {
  from { opacity: 0; transform: translateY(14px) scale(0.98); }
}

/* téléphone : plein écran */
@media (max-width: 767px) {
  .voile {
    padding: 0;
  }

  .lecteur {
    border: 0;
    border-radius: 0;
  }

  .entete {
    padding: 12px 8px 10px 14px;
  }

  .passage span {
    display: none;
  }

  .passage {
    width: 40px;
    padding: 0;
  }
}
</style>
