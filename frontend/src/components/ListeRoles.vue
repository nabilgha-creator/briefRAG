<script setup>
// rôles d'accès : nom, description, catégories consultables, nombre de comptes ; modification et suppression confirmée
import { ref } from 'vue'
import Icone from './Icone.vue'

defineProps({
  roles: { type: Array, default: () => [] },
  chargement: { type: Boolean, default: false },
})
const emit = defineEmits(['modifier', 'supprimer'])

const aSupprimer = ref(null)

function confirmer(role) {
  aSupprimer.value = null
  emit('supprimer', role)
}
</script>

<template>
  <div class="roles">
    <p v-if="chargement" class="vide">Chargement…</p>
    <p v-else-if="!roles.length" class="vide">Aucun rôle pour l'instant : créez-en un pour donner accès à la documentation.</p>
    <TransitionGroup name="carte" tag="div" class="grille">
      <article v-for="role in roles" :key="role.id_role" class="carte t">
        <div class="haut">
          <div class="titres">
            <h3>{{ role.nom }}</h3>
            <p v-if="role.description" class="description">{{ role.description }}</p>
          </div>
          <span class="mono comptes">{{ role.nombre_comptes }} compte{{ role.nombre_comptes > 1 ? 's' : '' }}</span>
        </div>

        <ul v-if="role.categories.length" class="categories" aria-label="Documents consultables">
          <li v-for="categorie in role.categories" :key="categorie" class="categorie">{{ categorie }}</li>
        </ul>
        <p v-else class="aucune">Aucun document consultable</p>

        <div v-if="aSupprimer === role.id_role" class="actions confirmation">
          <span>Supprimer ce rôle ?<template v-if="role.nombre_comptes"> {{ role.nombre_comptes }} compte(s) le perdront.</template></span>
          <button type="button" class="mini danger" @click="confirmer(role)">Oui</button>
          <button type="button" class="mini" @click="aSupprimer = null">Non</button>
        </div>
        <div v-else class="actions">
          <button type="button" class="bouton-icone" :aria-label="`Modifier le rôle ${role.nom}`" @click="emit('modifier', role)">
            <Icone nom="crayon" />
          </button>
          <button type="button" class="bouton-icone danger-icone" :aria-label="`Supprimer le rôle ${role.nom}`" @click="aSupprimer = role.id_role">
            <Icone nom="corbeille" />
          </button>
        </div>
      </article>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.vide {
  margin: 0;
  padding: 24px;
  border: 1px dashed var(--bordure2);
  border-radius: 18px;
  color: var(--discret);
  text-align: center;
}

.grille {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}

.carte {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px;
  border: 1px solid var(--bordure);
  border-radius: 18px;
  background-color: var(--carte);
  transition: border-color 0.2s, transform 0.2s;
}

.carte:hover {
  border-color: var(--bordure3);
  transform: translateY(-2px);
}

.haut {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.titres {
  min-width: 0;
}

h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
}

.description {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--doux);
}

.comptes {
  flex: none;
  padding: 4px 9px;
  border-radius: 999px;
  background-color: var(--eleve);
  font-size: 11px;
  color: var(--texte3);
}

.categories {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.categorie {
  padding: 5px 10px;
  border-radius: 999px;
  background-color: var(--acc-fond);
  color: var(--acc-texte);
  font-size: 12px;
  font-weight: 700;
}

.aucune {
  margin: 0;
  font-size: 13px;
  color: var(--erreur);
}

.actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 4px;
  margin-top: auto;
}

.confirmation span {
  margin-right: auto;
  font-size: 13px;
  font-weight: 600;
}

.danger-icone:hover {
  background-color: var(--erreur-fond);
  color: var(--erreur);
}

.mini {
  height: 34px;
  padding: 0 12px;
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

.carte-enter-active,
.carte-leave-active {
  transition: opacity 0.3s, transform 0.3s;
}

.carte-enter-from,
.carte-leave-to {
  opacity: 0;
  transform: scale(0.96);
}
</style>
