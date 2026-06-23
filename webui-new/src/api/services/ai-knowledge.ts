import client from "@/api/client"

export const aiKnowledgeService = {
  getState() { return client.get("/ai/knowledge/state").then(r => r.data) },
  setState(enabled: boolean) { return client.patch("/ai/knowledge/state", { enabled }).then(r => r.data) },
  listDocuments(params?: Record<string, unknown>) { return client.get("/ai/knowledge/documents", { params }).then(r => r.data) },
  upload(name: string, content: string) { return client.post("/ai/knowledge/documents", { source_file_name: name, content }).then(r => r.data) },
  getChunks(id: string) { return client.get(`/ai/knowledge/documents/${id}/chunks`).then(r => r.data) },
  rebuild(id: string) { return client.post(`/ai/knowledge/documents/${id}/rebuild`).then(r => r.data) },
  deleteDocument(id: string) { return client.delete(`/ai/knowledge/documents/${id}`).then(r => r.data) },
  retrievalPreview(query: string) { return client.post("/ai/knowledge/retrieval/preview", { query }).then(r => r.data) },
}
