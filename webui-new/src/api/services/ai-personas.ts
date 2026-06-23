import client from "@/api/client"

export const aiPersonasService = {
  list() { return client.get("/ai/personas").then(r => r.data) },
  upsert(data: Record<string, unknown>) { return client.put("/ai/personas", data).then(r => r.data) },
  getBindings() { return client.get("/ai/persona-bindings").then(r => r.data) },
}
