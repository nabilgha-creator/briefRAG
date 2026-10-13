import { defineStore } from 'pinia'

const CLE = 'briefrag.theme'

function themeInitial() {
  try {
    const enregistre = localStorage.getItem(CLE)
    if (enregistre === 'sombre' || enregistre === 'clair') return enregistre
  } catch {
    // stockage indisponible (navigation privée...) : on suit le système
  }
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'clair' : 'sombre'
}

/** thème sombre / clair, mémorisé dans le navigateur */
export const useThemeStore = defineStore('theme', {
  state: () => ({ theme: themeInitial() }),
  getters: {
    estSombre: (etat) => etat.theme === 'sombre',
  },
  actions: {
    appliquer() {
      const racine = document.documentElement
      racine.classList.toggle('theme-sombre', this.theme === 'sombre')
      racine.classList.toggle('theme-clair', this.theme === 'clair')
    },
    basculer() {
      this.theme = this.estSombre ? 'clair' : 'sombre'
      try {
        localStorage.setItem(CLE, this.theme)
      } catch {
        // pas de mémorisation possible : le thème vaut pour la session
      }
      this.appliquer()
    },
  },
})
