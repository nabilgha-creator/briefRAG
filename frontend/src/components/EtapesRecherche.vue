<script setup>
// étapes affichées pendant que l'assistant prépare sa réponse
import { computed } from 'vue'
import Icone from './Icone.vue'

const props = defineProps({
  phase: { type: String, default: 'analyse' },     // 'analyse' | 'recherche' | 'redaction'
})

const ETAPES = [
  { phase: 'analyse', libelle: 'analyse de la question' },
  { phase: 'recherche', libelle: 'recherche : fiches erreur + extraits' },
  { phase: 'redaction', libelle: 'rédaction de la réponse' },
]

const rang = computed(() => ETAPES.findIndex((etape) => etape.phase === props.phase))
</script>

<template>
  <ol class="etapes mono" aria-live="polite">
    <li v-for="(etape, index) in ETAPES" :key="etape.phase" class="etape apparition"
        :class="{ faite: index < rang, courante: index === rang, avenir: index > rang }" :style="{ animationDelay: `${index * 0.08}s` }">
      <Icone v-if="index < rang" nom="coche" :taille="16" :epaisseur="2.6" class="coche" />
      <span v-else-if="index === rang" class="roue-etape roue" aria-hidden="true"></span>
      <span v-else class="point" aria-hidden="true">·</span>
      <span>{{ etape.libelle }}</span>
    </li>
  </ol>
</template>

<style scoped>
.etapes {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 13px;
}

.etape {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--texte2);
  transition: color 0.3s;
}

.avenir {
  color: var(--tres-discret);
}

.coche {
  color: var(--succes);
}

.roue-etape {
  width: 14px;
  height: 14px;
  margin: 0 1px;
  border: 2.4px solid var(--acc2);
  border-right-color: transparent;
  border-radius: 50%;
}

.point {
  width: 16px;
  text-align: center;
}
</style>
