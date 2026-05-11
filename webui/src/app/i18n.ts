import { createI18n } from 'vue-i18n'
import enUS from '@/app/locales/en_US'
import zhCN from '@/app/locales/zh_CN'

export const SUPPORTED_LOCALES = ['zh_CN', 'en_US'] as const
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number]

const LOCALE_STORAGE_KEY = 'apeiria-locale'

export function normalizeLocale(value: unknown): SupportedLocale {
  return value === 'en_US' || value === 'zh_CN' ? value : 'zh_CN'
}

function readInitialLocale(): SupportedLocale {
  const stored = localStorage.getItem(LOCALE_STORAGE_KEY)
  if (stored === 'zh_CN' || stored === 'en_US') {
    return stored
  }
  return navigator.language.toLowerCase().startsWith('zh') ? 'zh_CN' : 'en_US'
}

const locale = readInitialLocale()

const i18n = createI18n({
  legacy: false,
  locale,
  fallbackLocale: 'zh_CN',
  messages: {
    zh_CN: zhCN,
    en_US: enUS,
  },
})

document.documentElement.lang = locale === 'zh_CN' ? 'zh-CN' : 'en-US'

export default i18n
