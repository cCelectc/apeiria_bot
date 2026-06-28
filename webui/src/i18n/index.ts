import { createI18n } from "vue-i18n";
import zhCN from "@/locales/zh-CN";

const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: "zh-CN",
  fallbackLocale: "zh-CN",
  missingWarn: false,
  missing: (_locale: string, key: string): string => {
    if (import.meta.env.DEV) {
      // eslint-disable-next-line no-console
      console.warn(`[i18n] missing key: ${key}`);
    }
    return key;
  },
  messages: { "zh-CN": zhCN },
});

export default i18n;
