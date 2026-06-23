import client from "@/api/client"

export const aiMemoriesService = {
  list(params?: Record<string, unknown>) { return client.get("/ai/memories", { params }).then(r => r.data) },
  create(data: Record<string, unknown>) { return client.post("/ai/memories", data).then(r => r.data) },
  update(data: Record<string, unknown>) { return client.patch("/ai/memories", data).then(r => r.data) },
  remove(memoryId: string) { return client.delete("/ai/memories", { params: { memory_id: memoryId } }).then(r => r.data) },
  setLifecycle(data: Record<string, unknown>) { return client.patch("/ai/memories/lifecycle", data).then(r => r.data) },
  bulkDelete(ids: string[]) { return client.post("/ai/memories/bulk-delete", { memory_ids: ids }).then(r => r.data) },
}
