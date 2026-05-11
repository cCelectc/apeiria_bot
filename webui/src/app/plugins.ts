import type { App } from 'vue'
import { createPinia } from 'pinia'
import { TooltipProvider } from '@/components/ui/tooltip'
import i18n from '@/app/i18n'
import router from '@/router'

export function registerPlugins(app: App) {
  app.use(createPinia())
  app.use(i18n)
  app.use(router)
  app.component('TooltipProvider', TooltipProvider)
}
