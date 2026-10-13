<script setup>
import Icone from './Icone.vue'
import { useThemeStore } from '@/stores/theme'

const theme = useThemeStore()
</script>

<template>
  <button type="button" class="bouton-icone bouton-theme" :aria-label="theme.estSombre ? 'Passer en mode clair' : 'Passer en mode sombre'"
          @click="theme.basculer()">
    <Transition name="icone-theme" mode="out-in">
      <Icone v-if="theme.estSombre" key="soleil" nom="soleil" :taille="20" />
      <Icone v-else key="lune" nom="lune" :taille="20" />
    </Transition>
  </button>
</template>

<style scoped>
.bouton-theme:hover {
  transform: rotate(-18deg);
}

.icone-theme-enter-active,
.icone-theme-leave-active {
  transition: opacity 0.2s, transform 0.25s;
}

.icone-theme-enter-from {
  opacity: 0;
  transform: rotate(-90deg) scale(0.6);
}

.icone-theme-leave-to {
  opacity: 0;
  transform: rotate(90deg) scale(0.6);
}
</style>
