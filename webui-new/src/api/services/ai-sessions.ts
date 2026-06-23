import client from "@/api/client"

export const aiSessionsService = {
  list(params?: Record<string, unknown>) { return client.get("/ai/managed-sessions", { params }).then(r => r.data) },
  get(id: string) { return client.get(`/ai/managed-sessions/${id}`).then(r => r.data) },
  toggleAi(id: string, enabled: boolean) { return client.patch(`/ai/managed-sessions/${id}/ai-enabled`, { enabled }).then(r => r.data) },
  setPersona(id: string, persona_id: string | null) { return client.patch(`/ai/managed-sessions/${id}/persona`, { persona_id }).then(r => r.data) },
  resetContext(id: string) { return client.post(`/ai/managed-sessions/${id}/context-reset`).then(r => r.data) },
  getProfiles() { return client.get("/ai/profiles").then(r => r.data) },
  getRelationships() { return client.get("/ai/relationships/list").then(r => r.data) },
  getScenes(params?: Record<string, unknown>) { return client.get("/ai/scenes", { params }).then(r => r.data) },
}
