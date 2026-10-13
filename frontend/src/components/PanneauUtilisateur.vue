<script setup>
// panneau latéral de création / modification d'un compte
import { computed, onMounted, ref } from 'vue'
import Icone from './Icone.vue'

const props = defineProps({
  utilisateur: { type: Object, default: null },     // null : création
  rolesDisponibles: { type: Array, default: () => [] },   // rôles d'accès a la documentation
  enregistrement: { type: Boolean, default: false },
  erreur: { type: String, default: '' },
})
const emit = defineEmits(['fermer', 'enregistrer'])

const LONGUEUR_MIN = 8
const modification = computed(() => props.utilisateur !== null)

const identifiant = ref(props.utilisateur?.identifiant ?? '')
const nom = ref(props.utilisateur?.nom ?? '')
const motDePasse = ref('')
const role = ref(props.utilisateur?.role ?? 'conseiller')
const rolesChoisis = ref(new Set(props.utilisateur?.roles?.map((r) => r.id_role) ?? []))
const premierChamp = ref(null)

function basculerRole(idRole) {
  const copie = new Set(rolesChoisis.value)
  if (copie.has(idRole)) copie.delete(idRole)
  else copie.add(idRole)
  rolesChoisis.value = copie
}

function memesRoles() {
  const avant = new Set(props.utilisateur?.roles?.map((r) => r.id_role) ?? [])
  return avant.size === rolesChoisis.value.size && [...avant].every((id) => rolesChoisis.value.has(id))
}

const problemes = computed(() => {
  const liste = []
  if (!modification.value && !/^[A-Za-z0-9._-]{3,50}$/.test(identifiant.value)) liste.push('identifiant : 3 caractères minimum (lettres, chiffres, point, tiret)')
  if (!nom.value.trim()) liste.push('nom affiché obligatoire')
  if ((!modification.value || motDePasse.value) && motDePasse.value.length < LONGUEUR_MIN) liste.push(`mot de passe : ${LONGUEUR_MIN} caractères minimum`)
  return liste
})

function enregistrer() {
  if (problemes.value.length || props.enregistrement) return
  if (modification.value) {
    const champs = {}
    if (nom.value.trim() !== props.utilisateur.nom) champs.nom = nom.value.trim()
    if (role.value !== props.utilisateur.role) champs.role = role.value
    if (motDePasse.value) champs.mot_de_passe = motDePasse.value
    if (!memesRoles()) champs.roles = [...rolesChoisis.value]
    emit('enregistrer', champs)
  } else {
    emit('enregistrer', { identifiant: identifiant.value.trim(), nom: nom.value.trim(), mot_de_passe: motDePasse.value,
                          role: role.value, roles: [...rolesChoisis.value] })
  }
}

onMounted(() => premierChamp.value?.focus())
</script>

<template>
  <div class="voile" @click.self="emit('fermer')" @keydown.esc="emit('fermer')">
    <form class="panneau t" :aria-label="modification ? 'Modifier le compte' : 'Ajouter un utilisateur'" novalidate @submit.prevent="enregistrer">
      <div class="entete">
        <h2>{{ modification ? 'Modifier le compte' : 'Nouvel utilisateur' }}</h2>
        <button type="button" class="bouton-icone" aria-label="Fermer" @click="emit('fermer')">
          <Icone nom="croix" :taille="20" :epaisseur="2.2" />
        </button>
      </div>

      <div class="groupe">
        <label for="n-identifiant" class="etiquette">Identifiant</label>
        <div class="champ">
          <input id="n-identifiant" ref="premierChamp" v-model="identifiant" class="mono" maxlength="50" placeholder="conseiller.04"
                 :disabled="modification" autocomplete="off">
        </div>
        <span class="aide">{{ modification ? "L'identifiant ne peut pas être modifié." : 'Lettres, chiffres, point, tiret ; 3 caractères minimum.' }}</span>
      </div>

      <div class="groupe">
        <label for="n-nom" class="etiquette">Nom affiché</label>
        <div class="champ">
          <input id="n-nom" v-model="nom" maxlength="150" placeholder="Prénom Nom" autocomplete="off">
        </div>
      </div>

      <div class="groupe">
        <label for="n-mdp" class="etiquette">{{ modification ? 'Nouveau mot de passe (facultatif)' : 'Mot de passe provisoire' }}</label>
        <div class="champ">
          <input id="n-mdp" v-model="motDePasse" type="password" maxlength="200" placeholder="8 caractères minimum" autocomplete="new-password">
        </div>
        <span v-if="modification" class="aide">Le changer ferme toutes les sessions de ce compte.</span>
      </div>

      <div class="groupe">
        <span id="n-role" class="etiquette">Type de compte</span>
        <div role="radiogroup" aria-labelledby="n-role" class="segments t">
          <button v-for="option in [{ valeur: 'conseiller', libelle: 'Conseiller' }, { valeur: 'admin', libelle: 'Administrateur' }]"
                  :key="option.valeur" type="button" role="radio" class="segment" :class="{ choisi: role === option.valeur }"
                  :aria-checked="role === option.valeur" @click="role = option.valeur">
            {{ option.libelle }}
          </button>
        </div>
      </div>

      <fieldset class="groupe roles-acces">
        <legend class="etiquette">Rôles d'accès à la documentation</legend>
        <p v-if="role === 'admin'" class="aide">Les administrateurs voient toute la documentation, quels que soient leurs rôles.</p>
        <p v-if="!rolesDisponibles.length" class="aide">Aucun rôle n'existe : créez-en un dans l'onglet « Rôles ».</p>
        <label v-for="r in rolesDisponibles" :key="r.id_role" class="case" :class="{ cochee: rolesChoisis.has(r.id_role) }">
          <input type="checkbox" :checked="rolesChoisis.has(r.id_role)" @change="basculerRole(r.id_role)">
          <span class="coche-visuelle" aria-hidden="true"><Icone v-if="rolesChoisis.has(r.id_role)" nom="coche" :taille="14" :epaisseur="3" /></span>
          <span class="case-textes">
            <span>{{ r.nom }}</span>
            <span class="case-detail">{{ r.categories.length ? r.categories.join(' · ') : 'aucun document' }}</span>
          </span>
        </label>
        <p v-if="role !== 'admin' && rolesDisponibles.length && !rolesChoisis.size" class="aide attention">
          Sans rôle, ce compte ne verra aucun document.
        </p>
      </fieldset>

      <Transition name="contenu">
        <p v-if="erreur" class="erreur" role="alert">
          <Icone nom="alerte" />
          <span>{{ erreur }}</span>
        </p>
      </Transition>
      <ul v-if="problemes.length && (identifiant || nom || motDePasse)" class="problemes">
        <li v-for="probleme in problemes" :key="probleme">{{ probleme }}</li>
      </ul>

      <div class="espace"></div>
      <div class="boutons">
        <button type="button" class="bouton-secondaire" @click="emit('fermer')">Annuler</button>
        <button type="submit" class="bouton-primaire" :disabled="problemes.length > 0 || enregistrement">
          {{ enregistrement ? 'Enregistrement…' : modification ? 'Enregistrer' : 'Créer le compte' }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.voile {
  position: fixed;
  inset: 0;
  z-index: 10;
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

.champ input:disabled {
  color: var(--discret);
}

.aide {
  font-size: 12px;
  color: var(--discret);
}

.segments {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px;
  padding: 4px;
  border-radius: 12px;
  background-color: var(--eleve);
}

.segment {
  height: 40px;
  border: 0;
  border-radius: 9px;
  background-color: transparent;
  color: var(--doux);
  font-weight: 700;
  font-size: 14px;
  transition: color 0.25s;
}

.segment.choisi {
  background-image: var(--degrade);
  color: var(--sur-acc);
}

.roles-acces {
  margin: 0;
  padding: 0;
  border: 0;
}

.roles-acces legend {
  padding: 0;
  margin-bottom: 8px;
}

.case {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 14px;
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

.case-textes {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.case-detail {
  font-size: 12px;
  font-weight: 400;
  color: var(--discret);
}

.attention {
  color: var(--erreur);
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

.problemes {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--doux);
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
