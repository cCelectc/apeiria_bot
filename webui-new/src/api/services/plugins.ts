import client from "@/api/client"

export interface PluginItem {
  module_name: string
  name: string
  description: string
  version: string
  enabled: boolean
}

export const pluginsService = {
  list() {
    return client.get<PluginItem[]>("/plugins/").then((r) => r.data)
  },

  getSettings(name: string) {
    return client.get(`/plugins/${name}/settings`).then((r) => r.data)
  },

  updateSettings(name: string, values: Record<string, unknown>) {
    return client.patch(`/plugins/${name}/settings`, values).then((r) => r.data)
  },

  toggle(name: string, enabled: boolean) {
    return client.patch(`/plugins/${name}/policy`, { enabled }).then((r) => r.data)
  },

  getReadme(name: string) {
    return client.get(`/plugins/${name}/readme`).then((r) => r.data)
  },
}
