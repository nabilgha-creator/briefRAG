import { createRouter, createWebHistory } from 'vue-router'
import { useSessionStore } from '@/stores/session'

const routes = [
  {
    path: '/connexion',
    name: 'connexion',
    component: () => import('@/views/ConnexionView.vue'),
    meta: { public: true, titre: 'Connexion' },
  },
  {
    path: '/',
    component: () => import('@/layouts/LayoutConsole.vue'),
    meta: { layout: 'console' },
    children: [
      { path: '', name: 'nouvelle', component: () => import('@/views/ChatView.vue'), meta: { titre: 'Nouvelle conversation' } },
      { path: 'conversations/:id(\\d+)', name: 'conversation', component: () => import('@/views/ChatView.vue'), props: true, meta: { titre: 'Conversation' } },
      { path: 'admin', name: 'admin', component: () => import('@/views/AdminView.vue'), meta: { admin: true, titre: 'Administration' } },
    ],
  },
  { path: '/:chemin(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// garde : connexion obligatoire, page admin réservée aux administrateurs
router.beforeEach(async (vers) => {
  const session = useSessionStore()
  if (vers.meta.public) return session.estConnecte && vers.name === 'connexion' ? { name: 'nouvelle' } : true
  if (!session.estConnecte) return { name: 'connexion' }
  if (!session.utilisateur) {
    try {
      await session.chargerUtilisateur()
    } catch {
      session.oublier()
      return { name: 'connexion', query: { expiree: '1' } }
    }
  }
  if (vers.meta.admin && !session.estAdmin) return { name: 'nouvelle' }
  return true
})

router.afterEach((vers) => {
  document.title = `${vers.meta.titre ?? 'Console'} — Console SAV`
})

export default router
