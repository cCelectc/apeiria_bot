import { createApp } from "vue"
import { createPinia } from "pinia"
import { createI18n } from "vue-i18n"
import App from "./App.vue"
import router from "./router"

import "./assets/index.css"

const app = createApp(App)

const i18n = createI18n({
  legacy: false,
  locale: "zh-CN",
  fallbackLocale: "en",
  messages: {
    "zh-CN": {},
    en: {},
  },
})

app.use(createPinia())
app.use(router)
app.use(i18n)

app.mount("#app")
