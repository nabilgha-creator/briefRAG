<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import Icone from '@/components/Icone.vue'
import MessageAssistant from '@/components/MessageAssistant.vue'
import PanneauSources from '@/components/PanneauSources.vue'
import ZoneSaisie from '@/components/ZoneSaisie.vue'
import { useConversationsStore } from '@/stores/conversations'

const props = defineProps({
  id: { type: String, default: null },        // présent sur /conversations/:id
})

const conversations = useConversationsStore()
const router = useRouter()

const brouillon = ref('')
const fil = ref(null)
const saisie = ref(null)
const erreurChargement = ref('')

const SUGGESTIONS = [
  'Que veut dire le code E23 sur un LV-200 ?',
  'Le FR-600 peut-il faire une pyrolyse ?',
  'Quelle est la garantie du moteur à induction ?',
  'Comment nettoyer le filtre de vidange d\'un WX-300 ?',
]

const titre = computed(() => conversations.active?.titre ?? 'Nouvelle conversation')
const vide = computed(() => !conversations.messages.length && !conversations.chargement)

// ouvre la conversation de l'adresse, ou repart d'une conversation vide
watch(() => props.id, async (id) => {
  erreurChargement.value = ''
  if (!id) {
    if (!conversations.envoiEnCours) conversations.nouvelle()
    return
  }
  try {
    await conversations.ouvrir(Number(id))
    defilerEnBas('instant')
  } catch (erreur) {
    erreurChargement.value = erreur.message
  }
}, { immediate: true })

function defilerEnBas(comportement = 'smooth') {
  nextTick(() => fil.value?.scrollTo({ top: fil.value.scrollHeight, behavior: comportement }))
}

// suit la réponse pendant qu'elle s'écrit
watch(() => conversations.messages.at(-1)?.contenu, () => defilerEnBas())

// une conversation créée a la 1re question : l'adresse est mise a jour tout de suite
// (ouvrir() ne recharge pas la conversation déjà active, le streaming continue)
watch(() => conversations.active?.id_conversation, (id) => {
  if (id && Number(props.id) !== id) router.replace({ name: 'conversation', params: { id } })
})

async function envoyer(question) {
  brouillon.value = ''
  defilerEnBas()
  await conversations.envoyer(question)
  saisie.value?.focus()
}

function estSelectionne(message) {
  const assistants = conversations.messages.filter((element) => element.role === 'assistant')
  const choisi = assistants.find((element) => element.id_message === conversations.idMessageSources) ?? assistants.at(-1)
  return choisi === message
}
</script>

<template>
  <div class="chat">
    <main class="principal">
      <header class="entete t">
        <h1>{{ titre }}</h1>
      </header>

      <div ref="fil" class="fil" aria-live="polite">
        <p v-if="erreurChargement" class="erreur" role="alert">
          <Icone nom="alerte" />
          <span>{{ erreurChargement }}</span>
        </p>

        <div v-if="vide && !erreurChargement" class="accueil apparition">
          <h2>Bonjour, quelle est votre question ?</h2>
          <p>Indiquez le modèle (WX-500, LV-200, FR-700…) et le code erreur ou le symptôme : la réponse cite ses sources.</p>
          <div class="suggestions">
            <button v-for="suggestion in SUGGESTIONS" :key="suggestion" type="button" class="suggestion" @click="envoyer(suggestion)">
              {{ suggestion }}
            </button>
          </div>
        </div>

        <template v-for="message in conversations.messages" :key="message.id_message">
          <div v-if="message.role === 'user'" class="question t apparition">{{ message.contenu }}</div>
          <MessageAssistant v-else class="apparition" :message="message" :phase="conversations.phase"
                            :source-active="conversations.sourceActive" :selectionne="estSelectionne(message)"
                            @choisir-source="(numero) => conversations.choisirSource(message.id_message, numero)" />
        </template>
      </div>

      <div class="bas">
        <p v-if="conversations.erreur" class="erreur" role="alert">
          <Icone nom="alerte" />
          <span>{{ conversations.erreur }}</span>
        </p>
        <ZoneSaisie ref="saisie" v-model="brouillon" :desactive="conversations.envoiEnCours" @envoyer="envoyer" />
      </div>
    </main>

    <PanneauSources :sources="conversations.sources" :source-active="conversations.sourceActive"
                    @choisir="(numero) => conversations.choisirSource(conversations.idMessageSources, numero)" />
  </div>
</template>

<style scoped>
.chat {
  flex: 999 1 820px;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
}

.principal {
  flex: 999 1 500px;
  min-width: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.entete {
  display: flex;
  align-items: center;
  min-height: 64px;
  padding: 12px 28px;
  border-bottom: 1px solid var(--bordure);
}

h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.fil {
  flex: 1;
  overflow-y: auto;
  padding: 26px 28px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.question {
  align-self: flex-end;
  max-width: min(560px, 85%);
  padding: 13px 16px;
  border-radius: 16px 16px 4px 16px;
  background-color: var(--eleve2);
  font-size: 15px;
  line-height: 1.55;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.accueil {
  margin: auto 0;
  max-width: 640px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.accueil h2 {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.5px;
  background-image: var(--degrade);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.accueil p {
  margin: 0;
  color: var(--doux);
  line-height: 1.6;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.suggestion {
  padding: 9px 14px;
  border: 1px solid var(--bordure2);
  border-radius: 999px;
  background-color: transparent;
  color: var(--texte3);
  font-size: 13px;
  text-align: left;
  transition: border-color 0.2s, color 0.2s, background-color 0.2s, transform 0.2s;
}

.suggestion:hover {
  border-color: var(--acc2);
  color: var(--acc-texte);
  background-color: var(--acc-fond2);
  transform: translateY(-1px);
}

.bas {
  padding: 12px 28px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.erreur {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  padding: 10px 14px;
  border-radius: 12px;
  background-color: var(--erreur-fond);
  color: var(--erreur);
  font-size: 14px;
  font-weight: 600;
}

@media (max-width: 900px) {
  .principal {
    height: auto;
    min-height: 70vh;
  }
}
</style>
