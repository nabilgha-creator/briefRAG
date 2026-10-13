<script setup>
import { RouterView } from 'vue-router'
import BarreLaterale from '@/components/BarreLaterale.vue'
</script>

<template>
  <div class="console t">
    <BarreLaterale />
    <RouterView v-slot="{ Component, route }">
      <Transition name="contenu" mode="out-in">
        <component :is="Component" :key="route.name === 'admin' ? 'admin' : 'chat'" />
      </Transition>
    </RouterView>
  </div>
</template>

<style scoped>
.console {
  min-height: 100vh;
  display: flex;
  flex-wrap: wrap;
  background-color: var(--fond);
}
</style>
