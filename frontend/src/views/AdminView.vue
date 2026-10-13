<script setup>
import { computed, onMounted, ref } from 'vue'

import Icone from '@/components/Icone.vue'
import Interrupteur from '@/components/Interrupteur.vue'
import ListeRoles from '@/components/ListeRoles.vue'
import PanneauRole from '@/components/PanneauRole.vue'
import PanneauUtilisateur from '@/components/PanneauUtilisateur.vue'
import { apiRoles, apiUtilisateurs } from '@/api/routes'
import { useSessionStore } from '@/stores/session'
import { dateLisible } from '@/utils/format'

const session = useSessionStore()

const onglet = ref('utilisateurs')
const utilisateurs = ref([])
const journal = ref([])
const chargement = ref(true)
const notification = ref(null)           // { type: 'succes' | 'erreur', texte }
const panneau = ref(null)                // null fermé, { utilisateur: null } création, { utilisateur } modification
const enregistrement = ref(false)
const erreurPanneau = ref('')
const aSupprimer = ref(null)
const roles = ref([])
const categories = ref([])
const panneauRole = ref(null)            // null fermé, { role: null } création, { role } modification
let minuteurNotification = 0

const adminsActifs = computed(() => utilisateurs.value.filter((u) => u.role === 'admin' && u.actif).length)
const resume = computed(() => {
  const actifs = utilisateurs.value.filter((u) => u.actif).length
  return `${utilisateurs.value.length} comptes, dont ${actifs} actifs · chaque tentative de connexion est journalisée`
})

function initiales(nom) {
  return nom.split(/\s+/).filter(Boolean).map((mot) => mot[0]).join('').slice(0, 2).toUpperCase()
}

// le dernier admin actif ne peut être ni désactivé ni supprimé (l'API le refuse aussi) ; on ne se supprime pas soi-même
function estProtege(utilisateur) {
  return utilisateur.role === 'admin' && utilisateur.actif && adminsActifs.value <= 1
}

function notifier(type, texte) {
  notification.value = { type, texte }
  clearTimeout(minuteurNotification)
  minuteurNotification = setTimeout(() => { notification.value = null }, 4000)
}

async function charger() {
  chargement.value = true
  try {
    ;[utilisateurs.value, journal.value, roles.value, categories.value] = await Promise.all([
      apiUtilisateurs.lister(), apiUtilisateurs.journal(100), apiRoles.lister(), apiRoles.categories(),
    ])
  } catch (erreur) {
    notifier('erreur', erreur.message)
  } finally {
    chargement.value = false
  }
}

function remplacer(utilisateur) {
  utilisateurs.value = utilisateurs.value.map((u) => (u.id_utilisateur === utilisateur.id_utilisateur ? utilisateur : u))
}

async function basculerActif(utilisateur) {
  try {
    remplacer(await apiUtilisateurs.modifier(utilisateur.id_utilisateur, { actif: !utilisateur.actif }))
    notifier('succes', `Compte ${utilisateur.identifiant} ${utilisateur.actif ? 'désactivé' : 'activé'}.`)
  } catch (erreur) {
    notifier('erreur', erreur.message)
  }
}

async function supprimer(utilisateur) {
  aSupprimer.value = null
  try {
    await apiUtilisateurs.supprimer(utilisateur.id_utilisateur)
    utilisateurs.value = utilisateurs.value.filter((u) => u.id_utilisateur !== utilisateur.id_utilisateur)
    notifier('succes', `Compte ${utilisateur.identifiant} supprimé.`)
  } catch (erreur) {
    notifier('erreur', erreur.message)
  }
}

function ouvrirPanneau(utilisateur = null) {
  erreurPanneau.value = ''
  panneau.value = { utilisateur }
}

async function enregistrer(champs) {
  enregistrement.value = true
  erreurPanneau.value = ''
  try {
    const existant = panneau.value.utilisateur
    if (existant) {
      if (Object.keys(champs).length) remplacer(await apiUtilisateurs.modifier(existant.id_utilisateur, champs))
      notifier('succes', `Compte ${existant.identifiant} modifié.`)
    } else {
      const cree = await apiUtilisateurs.creer(champs)
      utilisateurs.value = [...utilisateurs.value, { ...cree, nouveau: true }]
      notifier('succes', `Compte ${cree.identifiant} créé.`)
    }
    panneau.value = null
    roles.value = await apiRoles.lister()          // nombre de comptes par rôle
  } catch (erreur) {
    erreurPanneau.value = erreur.message
  } finally {
    enregistrement.value = false
  }
}

function ouvrirPanneauRole(role = null) {
  erreurPanneau.value = ''
  panneauRole.value = { role }
}

async function enregistrerRole(champs) {
  enregistrement.value = true
  erreurPanneau.value = ''
  try {
    const existant = panneauRole.value.role
    if (existant) await apiRoles.modifier(existant.id_role, champs)
    else await apiRoles.creer(champs)
    notifier('succes', `Rôle ${champs.nom} ${existant ? 'modifié' : 'créé'}.`)
    panneauRole.value = null
    ;[roles.value, utilisateurs.value] = await Promise.all([apiRoles.lister(), apiUtilisateurs.lister()])
  } catch (erreur) {
    erreurPanneau.value = erreur.message
  } finally {
    enregistrement.value = false
  }
}

async function supprimerRole(role) {
  try {
    await apiRoles.supprimer(role.id_role)
    notifier('succes', `Rôle ${role.nom} supprimé.`)
    ;[roles.value, utilisateurs.value] = await Promise.all([apiRoles.lister(), apiUtilisateurs.lister()])
  } catch (erreur) {
    notifier('erreur', erreur.message)
  }
}

async function voirJournal() {
  onglet.value = 'journal'
  try {
    journal.value = await apiUtilisateurs.journal(100)
  } catch (erreur) {
    notifier('erreur', erreur.message)
  }
}

onMounted(charger)
</script>

<template>
  <main class="admin">
    <div class="contenu">
      <div class="titre-page">
        <div>
          <h1>Comptes et connexions</h1>
          <p class="resume">{{ resume }}</p>
        </div>
        <button v-if="onglet === 'roles'" type="button" class="bouton-primaire" @click="ouvrirPanneauRole()">
          <Icone nom="plus" :epaisseur="2.4" />
          <span>Nouveau rôle</span>
        </button>
        <button v-else type="button" class="bouton-primaire" @click="ouvrirPanneau()">
          <Icone nom="plus" :epaisseur="2.4" />
          <span>Ajouter un utilisateur</span>
        </button>
      </div>

      <Transition name="contenu">
        <p v-if="notification" class="notification" :class="notification.type" role="status">
          <Icone :nom="notification.type === 'succes' ? 'coche' : 'alerte'" />
          <span>{{ notification.texte }}</span>
        </p>
      </Transition>

      <div role="tablist" aria-label="Sections" class="onglets t">
        <button type="button" role="tab" class="onglet" :class="{ actif: onglet === 'utilisateurs' }" :aria-selected="onglet === 'utilisateurs'"
                @click="onglet = 'utilisateurs'">Utilisateurs</button>
        <button type="button" role="tab" class="onglet" :class="{ actif: onglet === 'roles' }" :aria-selected="onglet === 'roles'"
                @click="onglet = 'roles'">Rôles d'accès</button>
        <button type="button" role="tab" class="onglet" :class="{ actif: onglet === 'journal' }" :aria-selected="onglet === 'journal'"
                @click="voirJournal">Journal des connexions</button>
      </div>

      <Transition name="contenu" mode="out-in">
        <section v-if="onglet === 'utilisateurs'" key="utilisateurs" class="tableau t">
          <table>
            <thead>
              <tr>
                <th>UTILISATEUR</th>
                <th>TYPE DE COMPTE</th>
                <th>RÔLES D'ACCÈS</th>
                <th>DERNIÈRE CONNEXION</th>
                <th>ACTIF</th>
                <th class="droite">ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="chargement"><td colspan="6" class="attente">Chargement…</td></tr>
              <tr v-for="u in utilisateurs" :key="u.id_utilisateur" class="ligne" :class="{ apparition: u.nouveau }">
                <td>
                  <div class="personne">
                    <div class="avatar" :class="{ eteint: !u.actif }" aria-hidden="true">{{ initiales(u.nom) }}</div>
                    <div class="identite">
                      <span class="nom">{{ u.nom }}<span v-if="u.id_utilisateur === session.utilisateur?.id_utilisateur" class="vous"> (vous)</span></span>
                      <span class="mono identifiant">{{ u.identifiant }}</span>
                    </div>
                  </div>
                </td>
                <td><span class="role" :class="u.role">{{ u.role === 'admin' ? 'Administrateur' : 'Conseiller' }}</span></td>
                <td>
                  <span v-if="u.role === 'admin'" class="discret petit-texte">toute la documentation</span>
                  <span v-else-if="!u.roles.length" class="sans-role">aucun</span>
                  <span v-else class="puces-roles">
                    <span v-for="r in u.roles" :key="r.id_role" class="puce-role">{{ r.nom }}</span>
                  </span>
                </td>
                <td class="date">{{ dateLisible(u.derniere_connexion) }}</td>
                <td>
                  <Interrupteur :actif="u.actif" :libelle="`${u.actif ? 'Désactiver' : 'Activer'} ${u.identifiant}`"
                                :desactive="estProtege(u)" @basculer="basculerActif(u)" />
                </td>
                <td>
                  <div v-if="aSupprimer === u.id_utilisateur" class="actions confirmation">
                    <span>Supprimer ce compte ?</span>
                    <button type="button" class="mini danger" @click="supprimer(u)">Oui</button>
                    <button type="button" class="mini" @click="aSupprimer = null">Non</button>
                  </div>
                  <div v-else class="actions">
                    <button type="button" class="bouton-icone" :aria-label="`Modifier ${u.identifiant}`" @click="ouvrirPanneau(u)">
                      <Icone nom="crayon" />
                    </button>
                    <button type="button" class="bouton-icone danger-icone" :aria-label="`Supprimer ${u.identifiant}`"
                            :disabled="estProtege(u) || u.id_utilisateur === session.utilisateur?.id_utilisateur" @click="aSupprimer = u.id_utilisateur">
                      <Icone nom="corbeille" />
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <p class="note">Le dernier administrateur actif ne peut être ni désactivé ni supprimé. Supprimer un compte supprime aussi ses conversations.</p>
        </section>

        <section v-else-if="onglet === 'roles'" key="roles">
          <ListeRoles :roles="roles" :chargement="chargement" @modifier="ouvrirPanneauRole" @supprimer="supprimerRole" />
        </section>

        <section v-else key="journal" class="tableau t">
          <table>
            <thead>
              <tr>
                <th>DATE</th>
                <th>IDENTIFIANT SAISI</th>
                <th>RÉSULTAT</th>
                <th>ADRESSE IP</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!journal.length"><td colspan="4" class="attente">Aucune connexion enregistrée.</td></tr>
              <tr v-for="entree in journal" :key="entree.id_connexion" class="ligne">
                <td class="date">{{ dateLisible(entree.date) }}</td>
                <td class="mono">{{ entree.identifiant }}</td>
                <td>
                  <span class="resultat" :class="entree.succes ? 'ok' : 'refus'">
                    <Icone :nom="entree.succes ? 'coche' : 'croix'" :taille="16" :epaisseur="2.4" />
                    {{ entree.succes ? 'Réussie' : 'Refusée' }}
                  </span>
                </td>
                <td class="mono discret">{{ entree.adresse_ip ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </Transition>
    </div>

    <PanneauUtilisateur v-if="panneau" :utilisateur="panneau.utilisateur" :roles-disponibles="roles" :enregistrement="enregistrement"
                        :erreur="erreurPanneau" @fermer="panneau = null" @enregistrer="enregistrer" />
    <PanneauRole v-if="panneauRole" :role="panneauRole.role" :categories="categories" :enregistrement="enregistrement"
                 :erreur="erreurPanneau" @fermer="panneauRole = null" @enregistrer="enregistrerRole" />
  </main>
</template>

<style scoped>
.admin {
  min-width: 0;
  height: 100vh;
  height: 100dvh;
  overflow-y: auto;
}

.contenu {
  max-width: 1080px;
  padding: 32px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.titre-page {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

h1 {
  margin: 0 0 6px;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.5px;
}

.resume {
  margin: 0;
  color: var(--doux);
}

.notification {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  padding: 12px 14px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
}

.notification.succes {
  background-color: var(--acc-fond);
  color: var(--acc-texte);
}

.notification.erreur {
  background-color: var(--erreur-fond);
  color: var(--erreur);
}

.onglets {
  display: flex;
  gap: 4px;
  padding: 4px;
  border-radius: 14px;
  background-color: var(--eleve);
  align-self: flex-start;
}

.onglet {
  padding: 10px 18px;
  border: 0;
  border-radius: 11px;
  background-color: transparent;
  color: var(--doux);
  font-weight: 600;
  font-size: 14px;
  transition: color 0.2s, background-color 0.2s;
}

.onglet:hover {
  color: var(--texte);
}

.onglet.actif {
  background-color: var(--panneau);
  color: var(--texte);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.tableau {
  border: 1px solid var(--bordure);
  border-radius: 18px;
  background-color: var(--carte);
  overflow-x: auto;
}

table {
  width: 100%;
  min-width: 720px;
  border-collapse: collapse;
  font-size: 14px;
}

th {
  padding: 14px 16px;
  text-align: left;
  font-family: var(--police-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.8px;
  color: var(--discret);
}

td {
  padding: 12px 16px;
  border-top: 1px solid var(--bordure);
}

.droite {
  text-align: right;
}

.ligne {
  transition: background-color 0.2s;
}

.ligne:hover {
  background-color: var(--eleve);
}

.attente {
  color: var(--discret);
  text-align: center;
  padding: 24px;
}

.personne {
  display: flex;
  align-items: center;
  gap: 12px;
}

.avatar {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 11px;
  background-color: var(--eleve2);
  color: var(--texte2);
  font-weight: 700;
  font-size: 13px;
  transition: opacity 0.3s;
}

.avatar.eteint {
  opacity: 0.5;
}

.identite {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.nom {
  font-weight: 600;
}

.vous {
  font-weight: 400;
  color: var(--discret);
}

.identifiant {
  font-size: 12px;
  color: var(--discret);
}

.role {
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  background-color: var(--acc-fond);
  color: var(--acc-texte);
}

.role.admin {
  background-color: var(--admin-fond);
  color: var(--admin-texte);
}

.date {
  color: var(--texte3);
}

.puces-roles {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.puce-role {
  padding: 4px 9px;
  border-radius: 999px;
  border: 1px solid var(--bordure2);
  font-size: 12px;
  font-weight: 600;
  color: var(--texte2);
  white-space: nowrap;
}

.sans-role {
  font-size: 13px;
  font-weight: 600;
  color: var(--erreur);
}

.petit-texte {
  font-size: 13px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 4px;
}

.confirmation span {
  margin-right: 6px;
  font-size: 13px;
  font-weight: 600;
}

.danger-icone:hover:not(:disabled) {
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

.resultat {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
}

.resultat.ok {
  color: var(--succes);
}

.resultat.refus {
  color: var(--erreur);
}

.discret {
  color: var(--discret);
}

.note {
  margin: 0;
  padding: 14px 16px;
  border-top: 1px solid var(--bordure);
  font-size: 13px;
  color: var(--doux);
}

@media (max-width: 767px) {
  .admin {
    height: calc(100dvh - 56px);      /* sous la barre du haut (LayoutConsole) */
  }

  .contenu {
    padding: 24px 16px;
  }
}
</style>
