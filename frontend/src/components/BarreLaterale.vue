<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import BoutonTheme from './BoutonTheme.vue'
import Icone from './Icone.vue'
import LogoMarque from './LogoMarque.vue'
import { useConversationsStore } from '@/stores/conversations'
import { useSessionStore } from '@/stores/session'
import { dateCourte } from '@/utils/format'

const session = useSessionStore()
const conversations = useConversationsStore()
const route = useRoute()
const router = useRouter()

const enEdition = ref(null)          // id de la conversation renommée
const titreEdite = ref('')
const aSupprimer = ref(null)         // id en attente de confirmation
const champTitre = ref(null)

onMounted(() => conversations.chargerListe().catch(() => {}))

function estActive(id) {
  return route.name === 'conversation' && Number(route.params.id) === id
}

function nouvelle() {
  conversations.nouvelle()
  router.push({ name: 'nouvelle' })
}

async function commencerRenommage(conversation) {
  enEdition.value = conversation.id_conversation
  titreEdite.value = conversation.titre
  await nextTick()
  champTitre.value?.[0]?.select()
}

async function validerRenommage(id) {
  const titre = titreEdite.value.trim()
  enEdition.value = null
  if (titre) await conversations.renommer(id, titre).catch(() => {})
}

async function supprimer(id) {
  aSupprimer.value = null
  const etaitOuverte = estActive(id)
  await conversations.supprimer(id).catch(() => {})
  if (etaitOuverte) router.push({ name: 'nouvelle' })
}
</script>

<template>
  <aside class="rail t">
    <div class="marque">
      <LogoMarque />
      <span class="marque-nom">CONSOLE SAV</span>
    </div>

    <button type="button" class="nouvelle" @click="nouvelle">
      <Icone nom="plus" :taille="16" :epaisseur="2.4" />
      <span>Nouvelle conversation</span>
    </button>

    <nav class="liste" aria-label="Conversations">
      <p v-if="!conversations.liste.length" class="vide">Aucune conversation pour l'instant.</p>
      <TransitionGroup name="liste" tag="ul">
        <li v-for="conversation in conversations.liste" :key="conversation.id_conversation" class="element"
            :class="{ active: estActive(conversation.id_conversation) }">
          <template v-if="enEdition === conversation.id_conversation">
            <label :for="`titre-${conversation.id_conversation}`" class="masque">Nouveau titre</label>
            <input :id="`titre-${conversation.id_conversation}`" ref="champTitre" v-model="titreEdite" class="edition" maxlength="150"
                   @keydown.enter.prevent="validerRenommage(conversation.id_conversation)" @keydown.esc="enEdition = null"
                   @blur="validerRenommage(conversation.id_conversation)">
          </template>
          <template v-else-if="aSupprimer === conversation.id_conversation">
            <span class="confirmation">Supprimer ?</span>
            <button type="button" class="mini danger" @click="supprimer(conversation.id_conversation)">Oui</button>
            <button type="button" class="mini" @click="aSupprimer = null">Non</button>
          </template>
          <template v-else>
            <RouterLink :to="{ name: 'conversation', params: { id: conversation.id_conversation } }" class="lien">
              <span class="titre">{{ conversation.titre }}</span>
              <span class="mono quand">{{ dateCourte(conversation.date_maj) }}</span>
            </RouterLink>
            <span class="actions">
              <button type="button" class="bouton-icone petit" :aria-label="`Renommer ${conversation.titre}`" @click="commencerRenommage(conversation)">
                <Icone nom="crayon" :taille="15" />
              </button>
              <button type="button" class="bouton-icone petit" :aria-label="`Supprimer ${conversation.titre}`" @click="aSupprimer = conversation.id_conversation">
                <Icone nom="corbeille" :taille="15" />
              </button>
            </span>
          </template>
        </li>
      </TransitionGroup>
    </nav>

    <div class="navigation">
      <RouterLink v-if="route.name === 'admin'" :to="{ name: 'nouvelle' }" class="lien-nav">
        <Icone nom="bulles" />
        <span>Conversations</span>
      </RouterLink>
      <RouterLink v-if="session.estAdmin" :to="{ name: 'admin' }" class="lien-nav" active-class="actif">
        <Icone nom="bouclier" />
        <span>Administration</span>
      </RouterLink>
    </div>

    <div class="utilisateur t">
      <div class="avatar" aria-hidden="true">{{ session.initiales }}</div>
      <div class="identite">
        <span class="nom">{{ session.utilisateur?.nom }}</span>
        <span class="mono role">{{ session.utilisateur?.role }}</span>
      </div>
      <BoutonTheme />
      <button type="button" class="bouton-icone" aria-label="Se déconnecter" @click="session.deconnecter()">
        <Icone nom="deconnexion" />
      </button>
    </div>
  </aside>
</template>

<style scoped>
.rail {
  flex: 1 1 250px;
  max-width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 14px;
  background-color: var(--rail);
  border-right: 1px solid var(--bordure);
  min-height: 100vh;
}

.marque {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 6px;
}

.marque-nom {
  font-weight: 700;
  letter-spacing: 1.5px;
  font-size: 13px;
}

.nouvelle {
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid var(--bordure2);
  border-radius: 12px;
  background-color: transparent;
  color: var(--texte3);
  font-weight: 600;
  font-size: 14px;
  transition: border-color 0.2s, color 0.2s, background-color 0.2s;
}

.nouvelle:hover {
  border-color: var(--acc2);
  color: var(--acc-texte);
  background-color: var(--acc-fond2);
}

.liste {
  flex: 1;
  overflow-y: auto;
  margin: 0 -4px;
  padding: 0 4px;
}

.liste ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.vide {
  margin: 8px 6px;
  font-size: 13px;
  color: var(--discret);
}

.element {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 52px;
  border-radius: 10px;
  transition: background-color 0.2s, transform 0.2s;
}

.element:hover {
  background-color: var(--eleve);
}

.element.active {
  background-color: var(--eleve2);
}

.lien {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 9px 12px;
  color: var(--texte2);
  text-decoration: none;
  transition: transform 0.2s;
}

.element:hover .lien {
  transform: translateX(3px);
}

.element.active .lien {
  color: var(--texte);
}

.titre {
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.quand {
  font-size: 11px;
  color: var(--discret);
}

.actions {
  display: flex;
  opacity: 0;
  transition: opacity 0.2s;
}

.element:hover .actions,
.element:focus-within .actions {
  opacity: 1;
}

.petit {
  width: 32px;
  height: 32px;
}

.edition {
  flex: 1;
  margin: 6px;
  height: 38px;
  padding: 0 10px;
  border: 1.5px solid var(--acc2);
  border-radius: 9px;
  background-color: var(--panneau);
  font-size: 14px;
}

.confirmation {
  flex: 1;
  padding-left: 12px;
  font-size: 13px;
  font-weight: 600;
}

.mini {
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--bordure2);
  border-radius: 8px;
  background-color: transparent;
  font-size: 13px;
  font-weight: 600;
}

.mini.danger {
  border-color: transparent;
  background-color: var(--erreur-fond);
  color: var(--erreur);
}

.mini:last-child {
  margin-right: 6px;
}

.navigation {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.lien-nav {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 12px;
  border-radius: 12px;
  color: var(--doux);
  text-decoration: none;
  font-weight: 600;
  font-size: 14px;
  transition: background-color 0.2s, color 0.2s;
}

.lien-nav:hover {
  background-color: var(--eleve);
  color: var(--acc-texte);
}

.lien-nav.actif {
  background-color: var(--eleve2);
  color: var(--texte);
}

.utilisateur {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px;
  border: 1px solid var(--bordure);
  border-radius: 12px;
  background-color: var(--carte);
}

.avatar {
  flex: none;
  width: 32px;
  height: 32px;
  margin-right: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  background-color: var(--acc-fond);
  color: var(--acc-texte);
  font-weight: 700;
  font-size: 13px;
}

.identite {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}

.nom {
  font-weight: 600;
  font-size: 13px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.role {
  font-size: 11px;
  color: var(--discret);
}

/* conversations qui arrivent / partent de la liste */
.liste-enter-active,
.liste-leave-active,
.liste-move {
  transition: opacity 0.3s, transform 0.3s;
}

.liste-enter-from,
.liste-leave-to {
  opacity: 0;
  transform: translateX(-12px);
}

.liste-leave-active {
  position: absolute;
  width: 100%;
}

@media (max-width: 900px) {
  .rail {
    min-height: 0;
    border-right: 0;
    border-bottom: 1px solid var(--bordure);
  }

  .liste {
    max-height: 220px;
  }
}
</style>
