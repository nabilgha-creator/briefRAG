<script setup>
// icônes en trait (stroke), décoratives : le texte ou l'aria-label du bouton parent porte le sens
defineProps({
  nom: { type: String, required: true },
  taille: { type: Number, default: 18 },
  epaisseur: { type: Number, default: 2 },
})

const TRACES = {
  plus: ['M12 5v14', 'M5 12h14'],
  envoyer: ['M12 19V5', 'M6 11l6-6 6 6'],
  fleche: ['M5 12h14', 'M13 6l6 6-6 6'],
  retour: ['M19 12H5', 'M11 6l-6 6 6 6'],
  deconnexion: ['M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3', 'M10 17l5-5-5-5', 'M15 12H4'],
  bouclier: ['M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6l8-3z'],
  bulles: ['M4 5h16v11H8l-4 4V5z'],
  soleil: ['M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z', 'M12 2v2', 'M12 20v2', 'M4.9 4.9l1.4 1.4', 'M17.7 17.7l1.4 1.4', 'M2 12h2', 'M20 12h2', 'M4.9 19.1l1.4-1.4', 'M17.7 6.3l1.4-1.4'],
  lune: ['M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z'],
  crayon: ['M4 20h4L19 9l-4-4L4 16v4z'],
  corbeille: ['M4 7h16', 'M9 7V4h6v3', 'M6 7l1 13h10l1-13'],
  croix: ['M6 6l12 12', 'M18 6L6 18'],
  coche: ['M5 12l5 5 9-10'],
  alerte: ['M12 3l9 16H3l9-16z', 'M12 10v4', 'M12 17h.01'],
  oeil: ['M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z', 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z'],
  oeilBarre: ['M3 3l18 18', 'M10.6 5.1A10.6 10.6 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.1', 'M6.6 6.6A17 17 0 0 0 2 12s3.5 7 10 7a10 10 0 0 0 5.4-1.6', 'M9.9 9.9a3 3 0 0 0 4.2 4.2'],
  copier: ['M9 9h11v11H9z', 'M5 15V6a2 2 0 0 1 2-2h9'],
  sources: ['M6 3h9l4 4v14H6z', 'M14 3v5h5', 'M9 13h7', 'M9 17h5'],
  menu: ['M4 6h16', 'M4 12h16', 'M4 18h16'],
  livre: ['M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z', 'M22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z'],
  telecharger: ['M12 3v12', 'M7 10l5 5 5-5', 'M5 21h14'],
  cible: ['M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10z', 'M12 2v3', 'M12 19v3', 'M2 12h3', 'M19 12h3'],
}
</script>

<template>
  <svg :width="taille" :height="taille" viewBox="0 0 24 24" fill="none" stroke="currentColor" :stroke-width="epaisseur"
       stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path v-for="trace in TRACES[nom]" :key="trace" :d="trace" />
  </svg>
</template>
