import { defineStore } from 'pinia'
import { apiAuth } from '@/api/routes'

const CLE = 'briefrag.jeton'

function lireJeton() {
  try {
    return localStorage.getItem(CLE)
  } catch {
    return null
  }
}

function ecrireJeton(jeton) {
  try {
    if (jeton) localStorage.setItem(CLE, jeton)
    else localStorage.removeItem(CLE)
  } catch {
    // stockage indisponible : la session ne survivra pas au rechargement
  }
}

/** utilisateur connecté et jeton de session */
export const useSessionStore = defineStore('session', {
  state: () => ({ jeton: lireJeton(), utilisateur: null }),
  getters: {
    estConnecte: (etat) => Boolean(etat.jeton),
    estAdmin: (etat) => etat.utilisateur?.role === 'admin',
    initiales: (etat) =>
      (etat.utilisateur?.nom ?? '')
        .split(/\s+/)
        .filter(Boolean)
        .map((mot) => mot[0])
        .join('')
        .slice(0, 2)
        .toUpperCase(),
  },
  actions: {
    async connecter(identifiant, motDePasse) {
      const { jeton, utilisateur } = await apiAuth.connexion(identifiant, motDePasse)
      this.jeton = jeton
      this.utilisateur = utilisateur
      ecrireJeton(jeton)
    },
    async chargerUtilisateur() {
      this.utilisateur = await apiAuth.moi()
    },
    oublier() {
      this.jeton = null
      this.utilisateur = null
      ecrireJeton(null)
    },
    async deconnecter() {
      try {
        await apiAuth.deconnexion()
      } finally {
        this.oublier()
        const { default: router } = await import('@/router')
        router.push({ name: 'connexion' })
      }
    },
    /** appelé par le client HTTP sur une réponse 401 */
    async sessionExpiree() {
      if (!this.jeton) return
      this.oublier()
      const { default: router } = await import('@/router')
      if (router.currentRoute.value.name !== 'connexion') router.push({ name: 'connexion', query: { expiree: '1' } })
    },
  },
})
