// accès HTTP a l'API : jeton, erreurs, flux SSE. VITE_API_URL : adresse de l'API (défaut /api, proxy Vite)
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

async function recuperer(chemin) {
  let reponse
  try {
    reponse = await fetch(BASE + chemin, { headers: entetes(false) })
  } catch {
    throw new ErreurApi(0, "impossible de joindre le serveur : l'API est-elle démarrée ?")
  }
  return verifier(reponse)
}

/** fichier binaire (pdf du lecteur) : un lien ou un iframe ne peut pas envoyer l'en-tête d'authentification */
export async function binaire(chemin) {
  return (await recuperer(chemin)).arrayBuffer()
}

/** télécharge un fichier protégé : récupéré avec le jeton, puis enregistré via un lien temporaire */
export async function telecharger(chemin, nomFichier) {
  const url = URL.createObjectURL(await (await recuperer(chemin)).blob())
  const lien = Object.assign(document.createElement('a'), { href: url, download: nomFichier })
  document.body.append(lien)
  lien.click()
  lien.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** réponse en SSE, lue avec fetch (EventSource ne fait ni POST ni en-tête d'authentification) ; gestionnaires { morceau, fin, erreur } */
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
