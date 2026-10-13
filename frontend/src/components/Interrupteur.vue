<script setup>
defineProps({
  actif: { type: Boolean, required: true },
  libelle: { type: String, required: true },
  desactive: { type: Boolean, default: false },
})
defineEmits(['basculer'])
</script>

<template>
  <button type="button" role="switch" class="interrupteur" :class="{ actif }" :aria-checked="actif" :aria-label="libelle"
          :disabled="desactive" @click="$emit('basculer')">
    <span class="curseur"></span>
  </button>
</template>

<style scoped>
.interrupteur {
  display: flex;
  width: 48px;
  height: 28px;
  padding: 3px;
  border: 0;
  border-radius: 999px;
  background-color: var(--off);
  transition: background-color 0.3s, box-shadow 0.3s;
}

.interrupteur.actif {
  background-image: var(--degrade);
  box-shadow: 0 4px 14px var(--halo);
}

.interrupteur:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.curseur {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background-color: #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
  transition: transform 0.3s cubic-bezier(0.2, 0.7, 0.2, 1);
}

.actif .curseur {
  transform: translateX(20px);
}
</style>
