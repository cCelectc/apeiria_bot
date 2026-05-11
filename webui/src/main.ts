import { createApp } from 'vue'
import '@fontsource/noto-sans-sc/400.css'
import '@fontsource/noto-sans-sc/500.css'
import '@fontsource/noto-sans-sc/700.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@/style.css'
import App from './App.vue'
import { registerPlugins } from './app/plugins'

const app = createApp(App)

registerPlugins(app)

app.mount('#app')
