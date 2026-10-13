<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import BoutonTheme from '@/components/BoutonTheme.vue'
import Icone from '@/components/Icone.vue'
import LogoMarque from '@/components/LogoMarque.vue'
import OrbiteAnimee from '@/components/OrbiteAnimee.vue'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const route = useRoute()
const router = useRouter()

const identifiant = ref('')
const motDePasse = ref('')
const motDePasseVisible = ref(false)
const envoi = ref(false)
const erreur = ref(route.query.expiree ? 'Votre session a expiré, reconnectez-vous.' : '')

const sousTitre = '> accès réservé aux conseillers'.split(' ')
const peutEnvoyer = computed(() => identifiant.value.trim() && motDePasse.value && !envoi.value)

async function seConnecter() {
  if (!peutEnvoyer.value) return
  envoi.value = true
  erreur.value = ''
  try {
    await session.connecter(identifiant.value.trim(), motDePasse.value)
    router.replace({ name: 'nouvelle' })
  } catch (probleme) {
    erreur.value = probleme.message
    motDePasse.value = ''
  } finally {
    envoi.value = false
  }
}
</script>

<template>
  <div class="connexion t">
    <OrbiteAnimee />
    <BoutonTheme class="theme" />

    <div class="contenu">
      <div class="marque apparition">
        <LogoMarque :taille="46" />
        <div class="marque-textes">
          <span class="marque-nom">ELECTRODOMUS</span>
          <span class="mono marque-sous">console SAV · interne</span>
        </div>
      </div>

      <form class="carte t apparition" novalidate @submit.prevent="seConnecter">
        <div class="entete">
          <h1>Connexion</h1>
          <p class="mono sous-titre">
            <span v-for="(mot, index) in sousTitre" :key="index" class="fondu-mot" :style="{ animationDelay: `${0.5 + index * 0.18}s` }">{{ mot }} </span>
          </p>
        </div>

        <Transition name="contenu">
          <p v-if="erreur" class="erreur" role="alert">
            <Icone nom="alerte" />
            <span>{{ erreur }}</span>
          </p>
        </Transition>

        <div class="groupe">
          <label for="identifiant" class="etiquette">Identifiant</label>
          <div class="champ">
            <input id="identifiant" v-model="identifiant" class="mono" type="text" autocomplete="username" placeholder="conseiller.01" required>
          </div>
        </div>

        <div class="groupe">
          <label for="mot-de-passe" class="etiquette">Mot de passe</label>
          <div class="champ champ-mdp">
            <input id="mot-de-passe" v-model="motDePasse" :type="motDePasseVisible ? 'text' : 'password'" autocomplete="current-password" placeholder="8 caractères minimum" required>
            <button type="button" class="bouton-icone" :aria-label="motDePasseVisible ? 'Masquer le mot de passe' : 'Afficher le mot de passe'"
                    @click="motDePasseVisible = !motDePasseVisible">
              <Icone :nom="motDePasseVisible ? 'oeilBarre' : 'oeil'" />
            </button>
          </div>
        </div>

        <button type="submit" class="bouton-primaire valider" :disabled="!peutEnvoyer">
          <span v-if="envoi" class="roue-chargement roue" aria-hidden="true"></span>
          <span>{{ envoi ? 'Connexion…' : 'Entrer dans la console' }}</span>
          <Icone v-if="!envoi" nom="fleche" class="fleche" :epaisseur="2.4" />
        </button>

        <p class="note">Compte créé par un administrateur. Chaque connexion est enregistrée.</p>
      </form>
    </div>
  </div>
</template>

<style scoped>
.connexion {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  background-color: var(--fond);
  background-image: linear-gradient(var(--grille) 1px, transparent 1px), linear-gradient(90deg, var(--grille) 1px, transparent 1px);
  background-size: 64px 64px;
  animation: lignes 6s linear infinite;
}

@keyframes lignes {
  to { background-position: 0 64px; }
}

.theme {
  position: absolute;
  top: 24px;
  right: 24px;
  border: 1px solid var(--bordure);
  background-color: var(--panneau);
}

.contenu {
  position: relative;
  width: 100%;
  max-width: 440px;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.marque {
  display: flex;
  align-items: center;
  gap: 14px;
}

.marque-textes {
  display: flex;
  flex-direction: column;
}

.marque-nom {
  font-weight: 700;
  letter-spacing: 2px;
  font-size: 14px;
}

.marque-sous {
  font-size: 12px;
  color: var(--doux);
}

.carte {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 32px;
  border: 1px solid var(--bordure);
  border-radius: 22px;
  background-color: var(--panneau);
  box-shadow: 0 30px 60px var(--ombre);
  animation-delay: 0.15s;
}

.entete {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.5px;
}

.sous-titre {
  margin: 0;
  font-size: 13px;
  color: var(--doux);
}

.groupe {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.champ-mdp {
  padding-right: 4px;
}

.erreur {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  padding: 12px 14px;
  border-radius: 12px;
  background-color: var(--erreur-fond);
  color: var(--erreur);
  font-size: 14px;
  font-weight: 600;
}

.valider {
  height: 52px;
  font-size: 16px;
}

.valider:hover:not(:disabled) .fleche {
  transform: translateX(4px);
}

.fleche {
  transition: transform 0.2s;
}

.roue-chargement {
  width: 16px;
  height: 16px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
}

.note {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--doux);
}
</style>
