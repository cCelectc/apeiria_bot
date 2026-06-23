import client from "@/api/client"
import type { SettingsFieldItem } from "@/types/settings"

export interface CoreSettingsData {
  fields: SettingsFieldItem[]
  values: Record<string, unknown>
}

export const coreService = {
  getSettings() {
    return client.get<CoreSettingsData>("/core/settings").then((r) => r.data)
  },

  getRawSettings() {
    return client.get<string>("/core/settings/raw").then((r) => r.data)
  },

  updateSettings(values: Record<string, unknown>) {
    return client.patch("/core/settings", values).then((r) => r.data)
  },

  updateRawSettings(raw: string) {
    return client.patch("/core/settings/raw", { content: raw }).then((r) => r.data)
  },

  validateRawSettings(raw: string) {
    return client.post("/core/settings/raw/validate", { content: raw }).then((r) => r.data)
  },
}
