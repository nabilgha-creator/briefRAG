import { createApp } from 'vue'
import { createPinia } from 'pinia'

import '@fontsource/space-grotesk/400.css'
import '@fontsource/space-grotesk/500.css'
import '@fontsource/space-grotesk/600.css'
import '@fontsource/space-grotesk/700.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/600.css'
import './styles/global.css'

import App from './App.vue'
import router from './router'
import { useThemeStore } from './stores/theme'

const app = createApp(App)
app.use(createPinia())
useThemeStore().appliquer()       // avant le premier affichage : pas de flash de l'autre thème
app.use(router)
app.mount('#app')
