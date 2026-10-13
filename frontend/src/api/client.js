/**
 * accès HTTP a l'API FastAPI : en-tête d'authentification, erreurs, flux server-sent events.
 * VITE_API_URL : adresse de l'API (défaut /api, redirigé par Vite en développement)
 */
import { useSessionStore } from '@/stores/session'

const BASE = import.meta.env.VITE_API_URL ?? '/api'

/** erreur renvoyée par l'API, avec son statut HTTP et son message lisible */
export class ErreurApi extends Error {
  constructor(statut, message) {
    super(message)
    this.statut = statut
  }
}

async function messageErreur(reponse) {
  try {
    const corps = await reponse.json()
    if (typeof corps.detail === 'string') return corps.detail
    if (Array.isArray(corps.detail)) return corps.detail.map((erreur) => erreur.msg).join(' ; ')   // validation 422
  } catch {
    // corps non JSON
  }
  return `erreur ${reponse.status}`
}

function entetes(avecCorps) {
  const resultat = {}
  if (avecCorps) resultat['Content-Type'] = 'application/json'
  const jeton = useSessionStore().jeton
  if (jeton) resultat.Authorization = `Bearer ${jeton}`
  return resultat
}

async function verifier(reponse) {
  if (reponse.ok) return reponse
  const message = await messageErreur(reponse)
  if (reponse.status === 401) useSessionStore().sessionExpiree()
  throw new ErreurApi(reponse.status, message)
}

/** requête JSON ; renvoie le corps décodé (null pour une réponse 204) */
export async function requete(methode, chemin, corps) {
  let reponse
  try {
    reponse = await fetch(BASE + chemin, {
      method: methode,
      headers: entetes(corps !== undefined),
      body: corps !== undefined ? JSON.stringify(corps) : undefined,
    })
  } catch {
    throw new ErreurApi(0, "impossible de joindre le serveur : l'API est-elle démarrée ?")
  }
  await verifier(reponse)
  return reponse.status === 204 ? null : reponse.json()
}

/**
 * requête dont la réponse arrive en server-sent events ("event: nom" + "data: {json}").
 * EventSource ne permet ni POST ni en-tête d'authentification : on lit le flux avec fetch.
 * gestionnaires : { morceau(donnees), fin(donnees), erreur(donnees) }, appelés selon le nom de l'événement
 */
export async function flux(chemin, corps, gestionnaires, signal) {
  let reponse
  try {
    reponse = await fetch(BASE + chemin, { method: 'POST', headers: entetes(true), body: JSON.stringify(corps), signal })
  } catch (erreur) {
    if (erreur.name === 'AbortError') return
    throw new ErreurApi(0, "impossible de joindre le serveur : l'API est-elle démarrée ?")
  }
  await verifier(reponse)

  const lecteur = reponse.body.getReader()
  const decodeur = new TextDecoder()
  let tampon = ''
  for (;;) {
    const { value, done } = await lecteur.read()
    if (done) break
    tampon += decodeur.decode(value, { stream: true })
    let separation
    while ((separation = tampon.indexOf('\n\n')) !== -1) {
      const bloc = tampon.slice(0, separation)
      tampon = tampon.slice(separation + 2)
      let nom = 'message'
      const donnees = []
      for (const ligne of bloc.split('\n')) {
        if (ligne.startsWith('event:')) nom = ligne.slice(6).trim()
        else if (ligne.startsWith('data:')) donnees.push(ligne.slice(5).trimStart())
      }
      gestionnaires[nom]?.(JSON.parse(donnees.join('\n') || '{}'))
    }
  }
}
