<script setup>
// structure des pages connectées : barre latérale fixe a gauche + contenu.
// sur téléphone (< 768 px) la barre latérale devient un menu escamotable
import { ref, watch } from 'vue'
import { RouterView, useRoute } from 'vue-router'

import BarreLaterale from '@/components/BarreLaterale.vue'
import Icone from '@/components/Icone.vue'
import LogoMarque from '@/components/LogoMarque.vue'

const route = useRoute()
const menuOuvert = ref(false)

watch(() => route.fullPath, () => { menuOuvert.value = false })    // le menu se referme après navigation
</script>

<template>
  <div class="console t">
    <header class="barre-mobile t">
      <button type="button" class="bouton-icone" aria-label="Ouvrir le menu" aria-controls="rail" :aria-expanded="menuOuvert"
              @click="menuOuvert = true">
        <Icone nom="menu" :taille="22" />
      </button>
      <LogoMarque :taille="30" />
      <span class="nom">CONSOLE SAV</span>
    </header>

    <Transition name="voile">
      <div v-if="menuOuvert" class="voile-menu" aria-hidden="true" @click="menuOuvert = false"></div>
    </Transition>

    <BarreLaterale id="rail" class="rail-console" :class="{ ouvert: menuOuvert }" @keydown.esc="menuOuvert = false" />

    <RouterView v-slot="{ Component, route: courante }">
      <Transition name="contenu" mode="out-in">
        <component :is="Component" :key="courante.name === 'admin' ? 'admin' : 'chat'" class="zone-contenu" />
      </Transition>
    </RouterView>
  </div>
</template>

<style scoped>
.console {
  display: grid;
  grid-template-columns: 264px minmax(0, 1fr);
  min-height: 100vh;
  background-color: var(--fond);
}

.barre-mobile {
  display: none;
}

.zone-contenu {
  min-width: 0;
}

@media (max-width: 767px) {
  .console {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto minmax(0, 1fr);
  }

  .barre-mobile {
    display: flex;
    align-items: center;
    gap: 10px;
    height: 56px;
    padding: 0 10px;
    border-bottom: 1px solid var(--bordure);
    background-color: var(--rail);
  }

  .nom {
    font-weight: 700;
    letter-spacing: 1.5px;
    font-size: 13px;
  }

  .console .rail-console {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 20;
    width: min(300px, 86vw);
    transform: translateX(-100%);
    transition: transform 0.3s cubic-bezier(0.2, 0.7, 0.2, 1);
    box-shadow: 24px 0 48px rgba(0, 0, 0, 0.25);
  }

  .console .rail-console.ouvert {
    transform: none;
  }

  .voile-menu {
    position: fixed;
    inset: 0;
    z-index: 15;
    background-color: var(--voile);
  }

  .voile-enter-active,
  .voile-leave-active {
    transition: opacity 0.25s;
  }

  .voile-enter-from,
  .voile-leave-to {
    opacity: 0;
  }
}
</style>
