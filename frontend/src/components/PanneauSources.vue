<script setup>
// sources de la réponse sélectionnée : type, titre, extrait, pertinence, fichier et pages
import { nextTick, ref, watch } from 'vue'

import Icone from './Icone.vue'
import { pagesLisibles, typeSource } from '@/utils/format'

const props = defineProps({
  sources: { type: Array, default: () => [] },
  sourceActive: { type: Number, default: null },
})
const emit = defineEmits(['choisir'])

const elements = ref({})

function pertinence(source) {
  if (source.distance === null || source.distance === undefined) return { largeur: '100%', mention: 'donnée exacte' }
  const pourcentage = Math.max(5, Math.min(100, Math.round((1 - source.distance) * 100)))
  return { largeur: `${pourcentage}%`, mention: `distance ${source.distance.toFixed(2).replace('.', ',')}` }
}

function emplacement(source) {
  const pages = pagesLisibles(source.pages)
  return pages ? `${source.source}, ${pages}` : source.source
}

// la source choisie (clic sur une citation) défile dans le panneau
watch(() => props.sourceActive, async (numero) => {
  if (numero === null) return
  await nextTick()
  elements.value[numero]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
})
</script>

<template>
  <aside class="panneau t" aria-label="Sources de la réponse">
    <div class="entete">
      <h2>Sources</h2>
      <span class="mono compte">{{ sources.length }} extrait{{ sources.length > 1 ? 's' : '' }}</span>
    </div>

    <div v-if="!sources.length" class="vide">
      <Icone nom="sources" :taille="28" :epaisseur="1.6" />
      <p>Les documents utilisés pour chaque réponse s'affichent ici.</p>
    </div>

    <TransitionGroup name="source" tag="div" class="liste">
      <button v-for="(source, index) in sources" :key="`${source.numero}-${source.source}`"
              :ref="(element) => { if (element) elements[source.numero] = element }"
              type="button" class="source" :class="{ active: source.numero === sourceActive }"
              :style="{ transitionDelay: `${index * 0.05}s` }" @click="emit('choisir', source.numero)">
        <span class="ligne">
          <span class="pastille">{{ source.numero }}</span>
          <span class="type">{{ typeSource(source.source) }}</span>
        </span>
        <span class="titre">{{ source.titre }}</span>
        <span v-if="source.extrait" class="extrait">{{ source.extrait }}</span>
        <span class="ligne">
          <span class="jauge"><span class="jauge-remplie" :style="{ width: pertinence(source).largeur }"></span></span>
          <span class="mono mention">{{ pertinence(source).mention }}</span>
        </span>
        <span class="mono chemin">{{ emplacement(source) }}</span>
      </button>
    </TransitionGroup>
  </aside>
</template>

<style scoped>
.panneau {
  flex: 1 1 320px;
  max-width: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px 18px;
  background-color: var(--rail);
  border-left: 1px solid var(--bordure);
  max-height: 100vh;
  overflow-y: auto;
  position: sticky;
  top: 0;
}

.entete {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.4px;
}

.compte {
  font-size: 11px;
  color: var(--discret);
}

.vide {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 40px 16px;
  color: var(--discret);
  text-align: center;
  font-size: 13px;
  line-height: 1.5;
}

.vide p {
  margin: 0;
}

.liste {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.source {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  border: 1px solid var(--bordure);
  border-radius: 14px;
  background-color: var(--carte);
  color: inherit;
  text-align: left;
  transition: border-color 0.3s, background-color 0.3s, transform 0.3s;
}

.source:hover {
  border-color: var(--bordure3);
  transform: translateX(-2px);
}

.source.active {
  border-color: var(--acc2);
  background-color: var(--acc-fond2);
  animation: signal 0.9s ease-out;
}

@keyframes signal {
  from { box-shadow: 0 0 0 0 var(--halo); }
  to { box-shadow: 0 0 0 14px transparent; }
}

.ligne {
  display: flex;
  align-items: center;
  gap: 10px;
}

.type {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.8px;
  color: var(--doux);
}

.titre {
  font-weight: 600;
  font-size: 14px;
  line-height: 1.35;
}

.extrait {
  font-size: 13px;
  line-height: 1.55;
  color: var(--doux);
}

.jauge {
  flex: 1;
  height: 4px;
  border-radius: 999px;
  background-color: var(--eleve2);
  overflow: hidden;
}

.jauge-remplie {
  display: block;
  height: 100%;
  border-radius: 999px;
  background-image: var(--degrade);
  transform-origin: left;
  animation: jauge 1.1s 0.2s cubic-bezier(0.2, 0.7, 0.2, 1) both;
}

@keyframes jauge {
  from { transform: scaleX(0); }
  to { transform: scaleX(1); }
}

.mention,
.chemin {
  font-size: 11px;
  color: var(--discret);
}

.chemin {
  overflow-wrap: anywhere;
}

.source-enter-active {
  transition: opacity 0.4s, transform 0.4s;
}

.source-enter-from {
  opacity: 0;
  transform: translateX(16px);
}

@media (max-width: 900px) {
  .panneau {
    position: static;
    max-height: none;
    border-left: 0;
    border-top: 1px solid var(--bordure);
  }
}
</style>
