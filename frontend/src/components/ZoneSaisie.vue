<script setup>
// fondu a la frappe : un <textarea> n'anime pas ses caractères, le texte est redessiné dessous (un <span> par
// caractère) ; le textarea, au texte transparent, garde curseur, sélection et copier-coller
import { computed, nextTick, ref, watch } from 'vue'
import Icone from './Icone.vue'

const props = defineProps({
  desactive: { type: Boolean, default: false },
  max: { type: Number, default: 2000 },
})
const emit = defineEmits(['envoyer'])
const texte = defineModel({ type: String, default: '' })

const champ = ref(null)
const miroir = ref(null)

const caracteres = computed(() => Array.from(texte.value))       // Array.from : les emojis comptent pour un caractère
const envoiPossible = computed(() => texte.value.trim().length > 0 && !props.desactive)

function envoyer() {
  if (!envoiPossible.value) return
  emit('envoyer', texte.value.trim())
}

function touche(evenement) {
  if (evenement.key === 'Enter' && !evenement.shiftKey && !evenement.isComposing) {
    evenement.preventDefault()
    envoyer()
  }
}

// le miroir défile avec le textarea quand le texte dépasse la hauteur maximale
function synchroniserDefilement() {
  if (miroir.value && champ.value) miroir.value.scrollTop = champ.value.scrollTop
}

watch(texte, () => nextTick(synchroniserDefilement))

defineExpose({ focus: () => champ.value?.focus() })
</script>

<template>
  <div class="zone">
    <div class="cadre t" :class="{ inactif: desactive }">
      <div class="saisie">
        <div ref="miroir" class="miroir" aria-hidden="true">
          <span v-for="(caractere, index) in caracteres" :key="index" class="caractere">{{ caractere }}</span><span class="fin">&#8203;</span>
        </div>
        <label for="question" class="masque">Votre question</label>
        <textarea id="question" ref="champ" v-model="texte" class="champ-texte" rows="1" :maxlength="max"
                  placeholder="Posez votre question… (Entrée pour envoyer)"
                  @keydown="touche" @scroll="synchroniserDefilement"></textarea>
      </div>
      <button type="button" class="envoi" :disabled="!envoiPossible" aria-label="Envoyer la question" @click="envoyer">
        <span v-if="desactive" class="roue-envoi roue" aria-hidden="true"></span>
        <Icone v-else nom="envoyer" :taille="20" :epaisseur="2.4" />
      </button>
    </div>
    <div class="pied mono">
      <span>Réponses fondées sur la documentation Electrodomus, sources citées entre crochets.</span>
      <span :class="{ limite: texte.length > max * 0.9 }">{{ texte.length }} / {{ max }}</span>
    </div>
  </div>
</template>

<style scoped>
.zone {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cadre {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 10px 10px 10px 16px;
  border: 1.5px solid var(--bordure2);
  border-radius: 18px;
  background-color: var(--panneau);
  transition: border-color 0.2s, box-shadow 0.2s, background-color 0.45s;
}

.cadre:focus-within {
  border-color: var(--acc2);
  box-shadow: 0 0 0 4px var(--halo);
}

.saisie {
  position: relative;
  flex: 1;
  min-width: 0;
}

/* miroir et textarea : exactement la même typographie et les mêmes marges, pour que les caractères se superposent */
.miroir,
.champ-texte {
  margin: 0;
  padding: 6px 0;
  border: 0;
  font-family: var(--police);
  font-size: 15px;
  line-height: 1.5;
  letter-spacing: normal;
  white-space: pre-wrap;
  overflow-wrap: break-word;
  word-break: break-word;
}

.miroir {
  min-height: 34.5px;      /* une ligne */
  max-height: 168px;       /* au-delà, les deux défilent */
  overflow: hidden;
  color: var(--texte);
}

.champ-texte {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  resize: none;
  overflow-y: auto;
  background: transparent;
  color: transparent;            /* le texte visible est celui du miroir */
  caret-color: var(--acc2);
}

.champ-texte::placeholder {
  color: var(--discret);
}

.champ-texte::selection {
  color: transparent;
  background-color: var(--halo);
}

/* chaque caractère tapé apparaît en fondu (seuls les nouveaux <span> jouent l'animation) */
.caractere {
  animation: fondu-caractere 0.35s ease-out both;
}

@keyframes fondu-caractere {
  from {
    opacity: 0;
    filter: blur(3px);
  }
  to {
    opacity: 1;
    filter: none;
  }
}

.envoi {
  flex: none;
  width: 46px;
  height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 13px;
  background-image: var(--degrade);
  color: var(--sur-acc);
  box-shadow: 0 8px 20px var(--halo);
  transition: transform 0.2s, filter 0.2s, opacity 0.2s;
}

.envoi:hover:not(:disabled) {
  transform: scale(1.06);
  filter: saturate(1.15) brightness(1.05);
}

.envoi:disabled {
  opacity: 0.4;
  cursor: default;
}

.inactif .envoi:disabled {
  opacity: 0.85;
}

.roue-envoi {
  width: 18px;
  height: 18px;
  border: 2.4px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
}

.pied {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 0 6px;
  font-size: 11px;
  color: var(--discret);
}

.limite {
  color: var(--acc-texte);
}
</style>
