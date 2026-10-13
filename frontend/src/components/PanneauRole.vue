<script setup>
// panneau latéral de création / modification d'un rôle d'accès : nom, description, catégories de documents lisibles
import { computed, onMounted, ref } from 'vue'
import Icone from './Icone.vue'

const props = defineProps({
  role: { type: Object, default: null },                 // null : création
  categories: { type: Array, default: () => [] },        // catégories attribuables
  enregistrement: { type: Boolean, default: false },
  erreur: { type: String, default: '' },
})
const emit = defineEmits(['fermer', 'enregistrer'])

const modification = computed(() => props.role !== null)
const nom = ref(props.role?.nom ?? '')
const description = ref(props.role?.description ?? '')
const choisies = ref(new Set(props.role?.categories ?? []))
const premierChamp = ref(null)

const valide = computed(() => nom.value.trim().length > 0)

function basculer(categorie) {
  const copie = new Set(choisies.value)
  if (copie.has(categorie)) copie.delete(categorie)
  else copie.add(categorie)
  choisies.value = copie
}

function toutes(cocher) {
  choisies.value = new Set(cocher ? props.categories : [])
}

function enregistrer() {
  if (!valide.value || props.enregistrement) return
  emit('enregistrer', { nom: nom.value.trim(), description: description.value.trim(), categories: [...choisies.value] })
}

onMounted(() => premierChamp.value?.focus())
</script>

<template>
  <div class="voile" @click.self="emit('fermer')" @keydown.esc="emit('fermer')">
    <form class="panneau t" :aria-label="modification ? 'Modifier le rôle' : 'Nouveau rôle'" novalidate @submit.prevent="enregistrer">
      <div class="entete">
        <h2>{{ modification ? 'Modifier le rôle' : 'Nouveau rôle' }}</h2>
        <button type="button" class="bouton-icone" aria-label="Fermer" @click="emit('fermer')">
          <Icone nom="croix" :taille="20" :epaisseur="2.2" />
        </button>
      </div>

      <div class="groupe">
        <label for="r-nom" class="etiquette">Nom du rôle</label>
        <div class="champ">
          <input id="r-nom" ref="premierChamp" v-model="nom" maxlength="50" placeholder="ex. Conseiller niveau 1" autocomplete="off">
        </div>
      </div>

      <div class="groupe">
        <label for="r-description" class="etiquette">Description (facultatif)</label>
        <div class="champ">
          <input id="r-description" v-model="description" maxlength="255" placeholder="À quoi sert ce rôle" autocomplete="off">
        </div>
      </div>

      <fieldset class="groupe categories">
        <legend class="etiquette">Documents consultables</legend>
        <div class="raccourcis">
          <button type="button" class="lien" @click="toutes(true)">Tout cocher</button>
          <button type="button" class="lien" @click="toutes(false)">Tout décocher</button>
        </div>
        <label v-for="categorie in categories" :key="categorie" class="case" :class="{ cochee: choisies.has(categorie) }">
          <input type="checkbox" :checked="choisies.has(categorie)" @change="basculer(categorie)">
          <span class="coche-visuelle" aria-hidden="true"><Icone v-if="choisies.has(categorie)" nom="coche" :taille="14" :epaisseur="3" /></span>
          <span>{{ categorie }}</span>
        </label>
        <p v-if="!choisies.size" class="aide">Aucune catégorie : les comptes ayant seulement ce rôle ne verront aucun document.</p>
        <p v-else-if="!choisies.has('Référentiel codes erreur')" class="aide">Sans le référentiel, les fiches erreur exactes ne sont pas fournies à l'assistant.</p>
      </fieldset>

      <Transition name="contenu">
        <p v-if="erreur" class="erreur" role="alert">
          <Icone nom="alerte" />
          <span>{{ erreur }}</span>
        </p>
      </Transition>

      <div class="espace"></div>
      <div class="boutons">
        <button type="button" class="bouton-secondaire" @click="emit('fermer')">Annuler</button>
        <button type="submit" class="bouton-primaire" :disabled="!valide || enregistrement">
          {{ enregistrement ? 'Enregistrement…' : modification ? 'Enregistrer' : 'Créer le rôle' }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.voile {
  position: fixed;
  inset: 0;
  z-index: 30;
  display: flex;
  justify-content: flex-end;
  background-color: var(--voile);
  animation: voile 0.25s ease both;
}

@keyframes voile {
  from { opacity: 0; }
}

.panneau {
  width: 100%;
  max-width: 440px;
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 32px 28px;
  background-color: var(--panneau);
  border-left: 1px solid var(--bordure);
  box-shadow: -24px 0 48px rgba(0, 0, 0, 0.25);
  animation: glisse 0.4s cubic-bezier(0.2, 0.7, 0.2, 1) both;
}

@keyframes glisse {
  from { opacity: 0; transform: translateX(48px); }
}

.entete {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
}

.groupe {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.champ {
  height: 48px;
}

.categories {
  margin: 0;
  padding: 0;
  border: 0;
}

.categories legend {
  padding: 0;
  margin-bottom: 8px;
}

.raccourcis {
  display: flex;
  gap: 14px;
}

.lien {
  padding: 0;
  border: 0;
  background: none;
  color: var(--acc-texte);
  font-size: 13px;
  font-weight: 600;
}

.case {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1.5px solid var(--bordure2);
  border-radius: 12px;
  background-color: var(--eleve);
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: border-color 0.2s, background-color 0.2s;
}

.case:hover {
  border-color: var(--bordure3);
}

.case.cochee {
  border-color: var(--acc2);
  background-color: var(--acc-fond2);
}

.case input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.case:has(input:focus-visible) {
  outline: 2px solid var(--acc2);
  outline-offset: 2px;
}

.coche-visuelle {
  flex: none;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid var(--bordure3);
  border-radius: 7px;
  transition: background-color 0.2s, border-color 0.2s;
}

.cochee .coche-visuelle {
  border-color: transparent;
  background-image: var(--degrade);
  color: var(--sur-acc);
}

.aide {
  margin: 0;
  font-size: 12px;
  color: var(--discret);
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

.espace {
  flex: 1;
}

.boutons {
  display: flex;
  gap: 10px;
}

.boutons > * {
  flex: 1;
}
</style>
