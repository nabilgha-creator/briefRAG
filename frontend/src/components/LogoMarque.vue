<script setup>
defineProps({
  taille: { type: Number, default: 34 },
})
</script>

<template>
  <div class="logo" :style="{ width: `${taille}px`, height: `${taille}px`, fontSize: `${Math.round(taille * 0.45)}px` }" aria-hidden="true">E</div>
</template>

<style scoped>
.logo {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 30%;
  background-image: var(--degrade);
  color: var(--sur-acc);
  font-weight: 700;
  box-shadow: 0 8px 20px var(--halo);
}
</style>
