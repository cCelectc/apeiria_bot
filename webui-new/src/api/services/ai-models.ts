import client from "@/api/client"

export interface AISource {
  source_id: string; name: string; provider: string
  api_base?: string; enabled?: boolean
}

export const aiModelsService = {
  getSources() { return client.get<AISource[]>("/ai/sources").then(r => r.data) },
  createSource(data: Record<string, unknown>) { return client.post("/ai/sources", data).then(r => r.data) },
  updateSource(data: Record<string, unknown>) { return client.put("/ai/sources", data).then(r => r.data) },
  deleteSource(id: string) { return client.delete("/ai/sources", { params: { source_id: id } }).then(r => r.data) },
  getModels(sourceId: string) { return client.get("/ai/sources/models", { params: { source_id: sourceId } }).then(r => r.data) },
  fetchModels(sourceId: string) { return client.post("/ai/sources/models/fetch", { source_id: sourceId }).then(r => r.data) },
}
