/** une fonction par route de l'API (cf. http://localhost:8000/docs) */
import { flux, requete } from './client'

export const apiAuth = {
  connexion: (identifiant, motDePasse) => requete('POST', '/auth/connexion', { identifiant, mot_de_passe: motDePasse }),
  deconnexion: () => requete('POST', '/auth/deconnexion'),
  moi: () => requete('GET', '/auth/moi'),
  changerMotDePasse: (ancien, nouveau) => requete('PUT', '/auth/moi/mot-de-passe', { ancien, nouveau }),
}

export const apiConversations = {
  lister: () => requete('GET', '/conversations'),
  creer: (titre) => requete('POST', '/conversations', titre ? { titre } : {}),
  detail: (id) => requete('GET', `/conversations/${id}`),
  renommer: (id, titre) => requete('PATCH', `/conversations/${id}`, { titre }),
  supprimer: (id) => requete('DELETE', `/conversations/${id}`),
  /** réponse au fil de l'eau : gestionnaires { morceau, fin, erreur } */
  poserQuestion: (id, question, gestionnaires, signal) => flux(`/conversations/${id}/messages/flux`, { question }, gestionnaires, signal),
}

export const apiRoles = {
  lister: () => requete('GET', '/roles'),
  categories: () => requete('GET', '/roles/categories'),
  creer: (role) => requete('POST', '/roles', role),
  modifier: (id, champs) => requete('PATCH', `/roles/${id}`, champs),
  supprimer: (id) => requete('DELETE', `/roles/${id}`),
}

export const apiUtilisateurs = {
  lister: () => requete('GET', '/utilisateurs'),
  creer: (utilisateur) => requete('POST', '/utilisateurs', utilisateur),
  modifier: (id, champs) => requete('PATCH', `/utilisateurs/${id}`, champs),
  supprimer: (id) => requete('DELETE', `/utilisateurs/${id}`),
  journal: (limite = 100) => requete('GET', `/utilisateurs/connexions?limite=${limite}`),
}
