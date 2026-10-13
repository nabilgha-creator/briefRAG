<script setup>
// élément graphique de fond de la connexion : anneaux en orbite, comètes, balayage, ondes.
// il suit doucement la souris (effet de profondeur) ; purement décoratif
import { onBeforeUnmount, onMounted, ref } from 'vue'

const decalage = ref({ x: 0, y: 0 })
let image = 0

function suivre(evenement) {
  cancelAnimationFrame(image)
  image = requestAnimationFrame(() => {
    decalage.value = {
      x: Math.round((evenement.clientX / window.innerWidth - 0.5) * -60),
      y: Math.round((evenement.clientY / window.innerHeight - 0.5) * -60),
    }
  })
}

onMounted(() => window.addEventListener('mousemove', suivre, { passive: true }))
onBeforeUnmount(() => {
  window.removeEventListener('mousemove', suivre)
  cancelAnimationFrame(image)
})
</script>

<template>
  <svg class="orbite" viewBox="0 0 800 800" aria-hidden="true"
       :style="{ transform: `translate(-28%, -50%) translate(${decalage.x}px, ${decalage.y}px)` }">
    <defs>
      <linearGradient id="orbite-trait" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" style="stop-color: var(--acc1)" />
        <stop offset="100%" style="stop-color: var(--acc2)" />
      </linearGradient>
      <radialGradient id="orbite-lueur" cx="50%" cy="50%" r="50%">
        <stop offset="0%" style="stop-color: var(--acc2); stop-opacity: 0.3" />
        <stop offset="100%" style="stop-color: var(--acc2); stop-opacity: 0" />
      </radialGradient>
      <linearGradient id="orbite-faisceau" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" style="stop-color: var(--acc1); stop-opacity: 0" />
        <stop offset="100%" style="stop-color: var(--acc1); stop-opacity: 0.22" />
      </linearGradient>
    </defs>
    <g class="derive">
      <circle class="coeur" cx="400" cy="400" r="230" fill="url(#orbite-lueur)" />
      <circle class="onde" cx="400" cy="400" r="96" fill="none" stroke="url(#orbite-trait)" stroke-width="1.5" vector-effect="non-scaling-stroke" />
      <circle class="onde onde-2" cx="400" cy="400" r="96" fill="none" stroke="url(#orbite-trait)" stroke-width="1.5" vector-effect="non-scaling-stroke" />
      <g class="balayage">
        <path d="M400 400 L400 40 A360 360 0 0 1 654.6 145.4 Z" fill="url(#orbite-faisceau)" />
      </g>
      <g class="anneau anneau-1" opacity="0.6">
        <circle cx="400" cy="400" r="360" fill="none" stroke="url(#orbite-trait)" stroke-width="1.2" stroke-dasharray="2 10" />
        <circle class="noeud" cx="760" cy="400" r="6" fill="url(#orbite-trait)" />
        <circle class="noeud noeud-3" cx="145" cy="655" r="4" fill="url(#orbite-trait)" />
        <rect x="380" y="28" width="40" height="26" rx="6" fill="none" stroke="url(#orbite-trait)" stroke-width="1.5" />
      </g>
      <g class="anneau anneau-2" opacity="0.75">
        <circle cx="400" cy="400" r="270" fill="none" stroke="url(#orbite-trait)" stroke-width="1.5" />
        <circle class="noeud noeud-2" cx="130" cy="400" r="7" fill="url(#orbite-trait)" />
        <circle class="noeud" cx="591" cy="591" r="5" fill="url(#orbite-trait)" />
        <circle class="noeud noeud-3" cx="591" cy="209" r="3.5" fill="url(#orbite-trait)" />
      </g>
      <circle class="comete" cx="400" cy="400" r="270" fill="none" stroke="url(#orbite-trait)" stroke-width="4" stroke-linecap="round" />
      <g class="anneau anneau-3" opacity="0.9">
        <circle cx="400" cy="400" r="180" fill="none" stroke="url(#orbite-trait)" stroke-width="2" stroke-dasharray="70 18 6 18" />
        <circle class="noeud" cx="400" cy="220" r="8" fill="url(#orbite-trait)" />
        <circle class="noeud noeud-2" cx="244" cy="490" r="4.5" fill="url(#orbite-trait)" />
      </g>
      <circle class="comete comete-2" cx="400" cy="400" r="180" fill="none" stroke="url(#orbite-trait)" stroke-width="3.5" stroke-linecap="round" />
      <circle cx="400" cy="400" r="96" fill="none" stroke="url(#orbite-trait)" stroke-width="1" opacity="0.55" />
    </g>
  </svg>
</template>

<style scoped>
.orbite {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 1100px;
  height: 1100px;
  max-width: none;
  pointer-events: none;
  transition: transform 0.9s cubic-bezier(0.2, 0.7, 0.2, 1);
}

/* toutes les rotations se font autour du centre du dessin */
.derive, .coeur, .onde, .balayage, .anneau {
  transform-box: view-box;
  transform-origin: 400px 400px;
}

.derive { animation: derive 16s ease-in-out infinite; }
.coeur { animation: respire 4s ease-in-out infinite; }
.onde { animation: onde 4.8s cubic-bezier(0.2, 0.6, 0.3, 1) infinite; }
.onde-2 { animation-delay: 2.4s; }
.balayage { animation: tourne 7s linear infinite; }
.anneau-1 { animation: tourne 34s linear infinite; }
.anneau-2 { animation: tourne 22s linear infinite reverse; }
.anneau-3 { animation: tourne 13s linear infinite; }

.noeud {
  transform-box: fill-box;
  transform-origin: center;
  animation: noeud 2.6s ease-in-out infinite;
}
.noeud-2 { animation-delay: 0.9s; }
.noeud-3 { animation-delay: 1.7s; }

/* la comète : un court trait qui parcourt le cercle (circonférence 2πr) */
.comete { stroke-dasharray: 90 1606; animation: comete 6s linear infinite; }
.comete-2 { stroke-dasharray: 50 1081; animation: comete-2 4.2s linear infinite; }

@keyframes derive {
  0%, 100% { transform: translate(0, 0); }
  33% { transform: translate(16px, -20px); }
  66% { transform: translate(-12px, 10px); }
}
@keyframes respire {
  0%, 100% { opacity: 0.55; transform: scale(1); }
  50% { opacity: 0.9; transform: scale(1.06); }
}
@keyframes onde {
  from { transform: scale(1); opacity: 0.7; }
  to { transform: scale(3.8); opacity: 0; }
}
@keyframes noeud {
  0%, 100% { transform: scale(1); opacity: 0.75; }
  50% { transform: scale(1.7); opacity: 1; }
}
@keyframes comete { to { stroke-dashoffset: -1696; } }
@keyframes comete-2 { to { stroke-dashoffset: 1131; } }
</style>
