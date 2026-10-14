import { defineStore } from 'pinia'
import { apiConversations } from '@/api/routes'
import { sansMarqueurSav } from '@/utils/format'

const DELAI_RECHERCHE = 700      // ms avant d'afficher l'étape "recherche" (la rédaction démarre au 1er morceau reçu)

let compteurLocal = 0
const idLocal = () => `local-${++compteurLocal}`

/** liste des conversations, conversation ouverte et envoi des questions (réponse en streaming) */
export const useConversationsStore = defineStore('conversations', {
  state: () => ({
    liste: [],
    active: null,               // { id_conversation, titre, messages: [...] }
    chargement: false,
    envoiEnCours: false,
    phase: null,                // 'analyse' | 'recherche' | 'redaction' pendant l'attente de la réponse
    idMessageSources: null,     // message dont le panneau affiche les sources
    sourceActive: null,         // numéro de la source mise en évidence
    erreur: null,
  }),
  getters: {
    messages: (etat) => etat.active?.messages ?? [],
    sources(etat) {
      const assistants = this.messages.filter((message) => message.role === 'assistant')
      const choisi = assistants.find((message) => message.id_message === etat.idMessageSources) ?? assistants.at(-1)
      return choisi?.sources ?? []
    },
  },
  actions: {
    async chargerListe() {
      this.liste = await apiConversations.lister()
    },
    nouvelle() {
      this.active = null
      this.idMessageSources = null
      this.sourceActive = null
      this.erreur = null
    },
    async ouvrir(id) {
      if (this.active?.id_conversation === id) return
      this.chargement = true
      this.erreur = null
      try {
        this.active = await apiConversations.detail(id)
        this.idMessageSources = null
        this.sourceActive = null
      } finally {
        this.chargement = false
      }
    },
    /** un 2e clic sur la même source la désélectionne */
    choisirSource(idMessage, numero) {
      const dejaChoisie = this.sourceActive === numero && this.idMessageSources === idMessage
      this.idMessageSources = idMessage
      this.sourceActive = dejaChoisie ? null : numero
    },
    async renommer(id, titre) {
      const conversation = await apiConversations.renommer(id, titre)
      Object.assign(this.liste.find((element) => element.id_conversation === id) ?? {}, conversation)
      if (this.active?.id_conversation === id) this.active.titre = conversation.titre
    },
    async supprimer(id) {
      await apiConversations.supprimer(id)
      this.liste = this.liste.filter((element) => element.id_conversation !== id)
      if (this.active?.id_conversation === id) this.nouvelle()
    },

    /**
     * envoie une question ; crée la conversation si besoin. renvoie l'id de la conversation
     * (la vue s'en sert pour mettre l'adresse a jour)
     */
    async envoyer(question) {
      if (this.envoiEnCours) return this.active?.id_conversation
      this.envoiEnCours = true
      this.erreur = null
      try {
        if (!this.active) {
          const conversation = await apiConversations.creer()
          this.active = { ...conversation, messages: [] }
          this.liste.unshift(conversation)
        }
        const conversation = this.active
        conversation.messages.push({ id_message: idLocal(), role: 'user', contenu: question, sources: null, date: new Date().toISOString() })
        conversation.messages.push({ id_message: idLocal(), role: 'assistant', contenu: '', sources: [], enCours: true, date: new Date().toISOString() })
        const reponse = conversation.messages.at(-1)       // l'objet réactif, pour le modifier au fil du flux

        this.phase = 'analyse'
        const minuteur = setTimeout(() => { if (this.phase === 'analyse') this.phase = 'recherche' }, DELAI_RECHERCHE)
        try {
          await apiConversations.poserQuestion(conversation.id_conversation, question, {
            morceau: ({ texte }) => {
              this.phase = 'redaction'
              reponse.contenu += texte
            },
            fin: ({ id_message, sources, consommation, contact_sav }) => {
              Object.assign(reponse, { id_message, sources, consommation, contact_sav, enCours: false, contenu: sansMarqueurSav(reponse.contenu) })
              this.idMessageSources = id_message
              this.sourceActive = null
            },
            erreur: ({ message }) => {
              Object.assign(reponse, { enCours: false, erreur: message })
            },
          })
        } catch (erreur) {
          Object.assign(reponse, { enCours: false, erreur: erreur.message })
        } finally {
          clearTimeout(minuteur)
          this.phase = null
          reponse.enCours = false
        }
        this.chargerListe().catch(() => {})      // titre (1re question) et ordre de la liste mis a jour
        return conversation.id_conversation
      } catch (erreur) {
        this.erreur = erreur.message
        return this.active?.id_conversation
      } finally {
        this.envoiEnCours = false
      }
    },
  },
})
