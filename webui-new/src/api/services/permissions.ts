import client from "@/api/client"

export interface AccessRule {
  subject_type: string
  subject_id: string
  plugin_module: string
  effect: "allow" | "deny"
}

export interface PluginAccessInfo {
  module_name: string
  access_mode: string
}

export const permissionsService = {
  listRules() {
    return client.get<AccessRule[]>("/permissions/rules").then((r) => r.data)
  },

  createRule(rule: AccessRule) {
    return client.post<AccessRule>("/permissions/rules", rule).then((r) => r.data)
  },

  deleteRule(rule: { subject_type: string; subject_id: string; plugin_module: string }) {
    return client.post("/permissions/rules/delete", rule).then((r) => r.data)
  },

  setPluginAccessMode(moduleName: string, mode: string) {
    return client.patch(`/permissions/plugins/${moduleName}/access-mode`, { mode }).then((r) => r.data)
  },
}
