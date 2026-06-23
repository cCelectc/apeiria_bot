import client from "@/api/client"

export const aiDebugService = {
  getTraces(params?: Record<string, unknown>) { return client.get("/ai/traces", { params }).then(r => r.data) },
  getUsageEvents(params?: Record<string, unknown>) { return client.get("/ai/usage-events", { params }).then(r => r.data) },
  getUsageSummary(params?: Record<string, unknown>) { return client.get("/ai/usage-summary", { params }).then(r => r.data) },
  getSkills() { return client.get("/ai/skills").then(r => r.data) },
  getTools() { return client.get("/ai/tools").then(r => r.data) },
}
